/* Local spatial studies. Procedural geometry, native WebGL, no network or dependencies.
 * The objects are conceptual art; they do not encode measurements or research results.
 * SpatialMotion.mount(canvas, {variant, intensity}) -> interaction / export controller.
 */
(() => {
  'use strict';
  const PI = Math.PI, TAU = PI * 2;
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const norm = a => { const q = Math.hypot(...a) || 1; return a.map(x => x / q); };
  const cross = (a, b) => [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]];
  const sub = (a, b) => a.map((x, i) => x-b[i]);
  const variants = new Set(['volume', 'tomography', 'field']);

  function multiply(a, b) {
    const r = new Float32Array(16);
    for (let c=0;c<4;c++) for(let row=0;row<4;row++)
      for(let k=0;k<4;k++) r[c*4+row] += a[k*4+row]*b[c*4+k];
    return r;
  }
  function rotation(x, y, z) {
    const sx=Math.sin(x),cx=Math.cos(x),sy=Math.sin(y),cy=Math.cos(y),sz=Math.sin(z),cz=Math.cos(z);
    return multiply(multiply(new Float32Array([cy,0,-sy,0, 0,1,0,0, sy,0,cy,0, 0,0,0,1]),
      new Float32Array([1,0,0,0, 0,cx,sx,0, 0,-sx,cx,0, 0,0,0,1])),
      new Float32Array([cz,sz,0,0, -sz,cz,0,0, 0,0,1,0, 0,0,0,1]));
  }
  function perspective(aspect, distance) {
    const f=1/Math.tan(34*PI/360),near=.1,far=30;
    const p=new Float32Array([f/aspect,0,0,0, 0,f,0,0, 0,0,(far+near)/(near-far),-1, 0,0,2*far*near/(near-far),0]);
    const v=new Float32Array([1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,-distance,1]);
    return multiply(p,v);
  }
  function transform(p,m) { return [m[0]*p[0]+m[4]*p[1]+m[8]*p[2],m[1]*p[0]+m[5]*p[1]+m[9]*p[2],m[2]*p[0]+m[6]*p[1]+m[10]*p[2]]; }

  // A volume sampled on one regular 3D lattice, clipped to a single asymmetric toroidal solid.
  // There is no random point placement or independent per-point blinking.
  function volumeGeometry() {
    const out=[];
    for(let x=-1.60;x<=1.60;x+=.064) for(let y=-1.10;y<=1.10;y+=.064) for(let z=-.68;z<=.68;z+=.064) {
      const q=Math.hypot(x/1.17,y/.83),tube=((q-1)/.32)**2+(z/.63)**2;
      if(tube>1) continue;
      const n=norm([x/1.17*(q-1)*3.1,y/.83*(q-1)*3.1,z*1.9]);
      out.push(x,y,z,...n,(x+1.6)/3.2,tube);
    }
    return new Float32Array(out);
  }

  function parametric(fn,nu,nv) {
    const out=[];
    function vertex(u,v) {
      const p=fn(u,v),du=sub(fn(u+.0001,v),fn(u-.0001,v)),dv=sub(fn(u,v+.0001),fn(u,v-.0001));
      return [...p,...norm(cross(du,dv)),u,v];
    }
    for(let i=0;i<nu;i++) for(let j=0;j<nv;j++) {
      const u=i/nu,v=j/nv,a=vertex(u,v),b=vertex((i+1)/nu,v),c=vertex((i+1)/nu,(j+1)/nv),d=vertex(u,(j+1)/nv);
      out.push(...a,...b,...c,...a,...c,...d);
    }
    return new Float32Array(out);
  }

  function corePoint(u,v,t=0) {
    const phase=t*TAU/8,phi=v*PI,theta=u*TAU,y=.90*Math.cos(phi);
    const radius=Math.sin(phi)*(.58+.09*Math.cos(phi*3+.22*Math.sin(phase)));
    const angle=theta+.42*Math.sin(phi*2)+.14*Math.sin(phase),shape=1+.16*Math.cos(theta*3+phi*1.8);
    return [radius*shape*Math.cos(angle)+.10*Math.sin(phi)*Math.sin(phi*2+.28*Math.sin(phase)),
      y+.027*Math.sin(theta)*Math.sin(phi)**2,.42*radius*shape*Math.sin(angle)+.045*Math.sin(phi)*Math.cos(phi*3)];
  }
  function sheetPoint(u,v,t=0) {
    const a=(u-.5)*2.74,b=(v-.5)*1.72,twist=a*1.42+.16*Math.sin(t*.48);
    return [a+.11*Math.sin(b*2.4+t*.38),b*Math.cos(twist)+.14*Math.sin(a*2.3+t*.48),
      b*Math.sin(twist)+.13*Math.cos(a*2.5+t*.48)];
  }
  function roundedBox() {
    const out=[],h=[.88,1.04,.40],r=.105,n=14;
    for(let face=0;face<6;face++) {
      const axis=Math.floor(face/2),sign=face%2?1:-1,a=(axis+1)%3,b=(axis+2)%3;
      function vertex(u,v) {
        const p=[0,0,0];p[axis]=sign*h[axis];p[a]=(u*2-1)*h[a];p[b]=(v*2-1)*h[b];
        const inner=p.map((x,i)=>clamp(x,-h[i]+r,h[i]-r)),normal=norm(sub(p,inner));
        const q=inner.map((x,i)=>x+normal[i]*r);
        q[0]+=.18*q[1]; // The slant belongs to the solid, not a 2D silhouette.
        const nn=norm([normal[0],normal[1]-.18*normal[0],normal[2]]);
        return [...q,...nn,u,v];
      }
      for(let i=0;i<n;i++) for(let j=0;j<n;j++) {
        const a0=vertex(i/n,j/n),a1=vertex((i+1)/n,j/n),a2=vertex((i+1)/n,(j+1)/n),a3=vertex(i/n,(j+1)/n);
        if(sign>0) out.push(...a0,...a1,...a2,...a0,...a2,...a3);
        else out.push(...a0,...a2,...a1,...a0,...a3,...a2);
      }
    }
    return new Float32Array(out);
  }
  const cpuGeometry={
    volume:volumeGeometry(),box:roundedBox(),
    core:parametric(corePoint,48,58),sheet:parametric(sheetPoint,76,40),
    plane:parametric((u,v)=>[(u-.5)*2.27,0,(v-.5)*1.26],1,1)
  };

  const vertexShader=`
    precision highp float;
    attribute vec3 aPosition; attribute vec3 aNormal; attribute vec2 aUV;
    uniform mat4 uModel,uViewProjection; uniform float uTime,uKind,uScan,uPointScale,uDistance,uIntensity;
    varying vec3 vWorld,vNormal,vLocal; varying vec2 vUV; varying float vBand;
    vec3 sheet(vec2 uv){
      float a=(uv.x-.5)*2.74,b=(uv.y-.5)*1.72,tw=a*1.42+.16*sin(uTime*.48);
      return vec3(a+.11*sin(b*2.4+uTime*.38),b*cos(tw)+.14*sin(a*2.3+uTime*.48),b*sin(tw)+.13*cos(a*2.5+uTime*.48));
    }
    vec3 core(vec2 uv){
      float phase=uTime*.7853981633974483,phi=uv.y*3.141592653589793,theta=uv.x*6.283185307179586,y=.90*cos(phi);
      float radius=sin(phi)*(.58+.09*cos(phi*3.+.22*sin(phase)));
      float angle=theta+.42*sin(phi*2.)+.14*sin(phase),shape=1.+.16*cos(theta*3.+phi*1.8);
      return vec3(radius*shape*cos(angle)+.10*sin(phi)*sin(phi*2.+.28*sin(phase)),
        y+.027*sin(theta)*sin(phi)*sin(phi),.42*radius*shape*sin(angle)+.045*sin(phi)*cos(phi*3.));
    }
    void main(){
      vec3 p=aPosition,n=aNormal;
      if(uKind<.5){
        p.x+=.036*sin(p.y*3.+uTime*.6);p.z+=.028*cos(p.y*3.+uTime*.6);
      }else if(uKind>1.5&&uKind<2.5){
        p=core(aUV);n=cross(core(aUV+vec2(.0005,0.))-core(aUV-vec2(.0005,0.)),core(aUV+vec2(0.,.0005))-core(aUV-vec2(0.,.0005)));
        n=length(n)<.0000001?vec3(0.,sign(.5-aUV.y),0.):normalize(n);
      }else if(uKind>2.5&&uKind<3.5){
        p=sheet(aUV);n=normalize(cross(sheet(aUV+vec2(.0005,0.))-sheet(aUV-vec2(.0005,0.)),sheet(aUV+vec2(0.,.0005))-sheet(aUV-vec2(0.,.0005))));
      }else if(uKind>3.5){p.y=uScan;}
      vec4 world=uModel*vec4(p,1.);vWorld=world.xyz;vNormal=mat3(uModel)*n;vLocal=p;vUV=aUV;
      vBand=exp(-pow((p.x-1.65*sin(uTime*1.15))/.19,2.));
      gl_Position=uViewProjection*world;
      gl_PointSize=clamp(uPointScale/(uDistance-world.z),2.,17.);
    }`;
  const fragmentShader=`
    precision highp float;
    uniform float uTime,uKind,uScan,uDistance,uIntensity,uShellAlpha;
    varying vec3 vWorld,vNormal,vLocal; varying vec2 vUV; varying float vBand;
    void main(){
      vec3 eye=normalize(vec3(0.,0.,uDistance)-vWorld),n=normalize(vNormal);
      vec3 key=normalize(vec3(-.65,.85,1.25)),fill=normalize(vec3(.9,-.15,-.4));
      vec3 plum=vec3(.32,.24,.43),pearl=vec3(.73,.66,.82),gold=vec3(.82,.60,.29),ivory=vec3(1.,.89,.67);
      float alpha=1.,band=0.;vec3 base;
      if(uKind<.5){
        vec2 q=gl_PointCoord*2.-1.;float r2=dot(q,q);if(r2>.97)discard;
        vec3 bead=normalize(vec3(q.x,-q.y,sqrt(max(0.,1.-r2))));
        float macro=.55+.45*max(0.,dot(n,key));
        float light=.22+.72*max(0.,dot(bead,key));
        float spec=pow(max(0.,dot(bead,normalize(key+vec3(0.,0.,1.)))),24.);
        base=mix(plum,pearl,.40+.28*vLocal.y)*light*macro;
        base+=pearl*.12*pow(1.-bead.z,2.);
        base=mix(base,gold*light+ivory*spec*.5,vBand*.84*uIntensity)+ivory*spec*.25;
        gl_FragColor=vec4(base,1.);return;
      }
      if(!gl_FrontFacing)n=-n;
      float ndl=max(0.,dot(n,key)),back=max(0.,dot(n,fill));
      float rim=pow(1.-abs(dot(n,eye)),2.6);
      float spec=pow(max(0.,dot(n,normalize(key+eye))),52.);
      if(uKind<1.5){
        // A closed beveled solid: broad ceramic reflection, transparent face, dense polished bevel.
        band=1.-smoothstep(.012,.033,abs(vLocal.y-uScan));
        base=mix(plum,pearl,.18+ndl*.40)*(.35+ndl*.58+back*.18);
        base+=pearl*rim*.28+vec3(.88,.82,.97)*spec*.65;
        base=mix(base,gold*.9+ivory*.28,band*.18*uIntensity);
        alpha=clamp(uShellAlpha+rim*.25+spec*.19+band*.08,.06,.88);
      }else if(uKind<2.5){
        band=exp(-pow((vLocal.y-uScan)/.045,2.));
        base=mix(plum*.72,pearl*.60,.24+ndl*.26)*(.30+ndl*.64+back*.18);
        float wideSpec=pow(max(0.,dot(n,normalize(key+eye))),14.);
        base+=pearl*rim*.15+ivory*wideSpec*.25;
        base=mix(base,gold*(.64+ndl*.6)+ivory*.33,band*.9*uIntensity);
        alpha=.94;
      }else if(uKind<3.5){
        float phase=vUV.x*8.-vUV.y*2.6-uTime*.92;
        band=pow(.5+.5*cos(phase),15.);
        base=mix(plum,pearl,.40+ndl*.30)*(.30+ndl*.66+back*.16);
        base+=pearl*rim*.40+ivory*spec*.78;
        base=mix(base,gold*(.58+ndl*.64)+ivory*spec*.7,band*.72*uIntensity);
        alpha=.89;
      }else{
        float edge=pow(max(abs(vUV.x-.5),abs(vUV.y-.5))*2.,12.);
        base=gold*.30+ivory*.07;alpha=.035+edge*.055;
      }
      float fog=clamp((vWorld.z+1.9)/4.2,.18,1.);
      base*=.68+.32*fog;
      gl_FragColor=vec4(base,alpha);
    }`;
  const postVertex=`attribute vec2 aPosition;varying vec2 vUV;void main(){vUV=aPosition*.5+.5;gl_Position=vec4(aPosition,0.,1.);}`;
  const postFragment=`
    precision highp float;varying vec2 vUV;uniform sampler2D uScene;uniform vec2 uResolution;uniform float uIntensity;
    vec3 bright(vec2 uv){vec3 c=texture2D(uScene,uv).rgb;return c*max(0.,max(c.r,max(c.g,c.b))-.52);}
    void main(){
      vec2 p=vUV-.5;float glow=exp(-dot(p*vec2(1.5,1.),p*vec2(1.5,1.))*8.);
      float edgeFade=smoothstep(0.,.20,min(min(vUV.x,1.-vUV.x),min(vUV.y,1.-vUV.y)));
      vec3 bg=vec3(.035294117647,.035294117647,.050980392157)+vec3(.013,.007,.020)*glow*edgeFade;
      bg+=vec3(.013,.009,.019)*exp(-dot((p-vec2(0.,-.29))*vec2(1.8,5.),(p-vec2(0.,-.29))*vec2(1.8,5.))*4.)*edgeFade;
      vec4 scene=texture2D(uScene,vUV);vec2 d=vec2(2.6)/uResolution;
      vec3 bloom=bright(vUV)*.24;
      bloom+=(bright(vUV+d*vec2(1.,0.))+bright(vUV+d*vec2(-1.,0.))+bright(vUV+d*vec2(0.,1.))+bright(vUV+d*vec2(0.,-1.)))*.12;
      bloom+=(bright(vUV+d*vec2(2.,2.))+bright(vUV+d*vec2(-2.,2.))+bright(vUV+d*vec2(2.,-2.))+bright(vUV+d*vec2(-2.,-2.)))*.07;
      vec3 c=bg*(1.-scene.a)+scene.rgb+bloom*.42*uIntensity;
      float grain=fract(sin(dot(gl_FragCoord.xy,vec2(12.9898,78.233)))*43758.5453)-.5;
      c+=grain*.0025*edgeFade;
      gl_FragColor=vec4(c,1.);
    }`;

  function compile(gl,type,source) {
    const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);
    if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)){const message=gl.getShaderInfoLog(s);gl.deleteShader(s);throw Error(message);}
    return s;
  }
  function program(gl,vs,fs) {
    const p=gl.createProgram(),a=compile(gl,gl.VERTEX_SHADER,vs),b=compile(gl,gl.FRAGMENT_SHADER,fs);
    gl.attachShader(p,a);gl.attachShader(p,b);gl.linkProgram(p);gl.deleteShader(a);gl.deleteShader(b);
    if(!gl.getProgramParameter(p,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(p));
    return p;
  }

  function webGLRenderer(canvas) {
    const gl=canvas.getContext('webgl',{alpha:false,antialias:true,depth:true,powerPreference:'high-performance',preserveDrawingBuffer:true});
    if(!gl)return null;
    const p=program(gl,vertexShader,fragmentShader),post=program(gl,postVertex,postFragment);
    const names=['uModel','uViewProjection','uTime','uKind','uScan','uPointScale','uDistance','uIntensity','uShellAlpha'];
    const loc=Object.fromEntries(names.map(k=>[k,gl.getUniformLocation(p,k)]));
    const pos=gl.getAttribLocation(p,'aPosition'),normal=gl.getAttribLocation(p,'aNormal'),uv=gl.getAttribLocation(p,'aUV');
    const mesh={};for(const [key,data]of Object.entries(cpuGeometry)){
      const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,data,gl.STATIC_DRAW);mesh[key]={buffer,count:data.length/8};
    }
    const quad=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,quad);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);
    const postPos=gl.getAttribLocation(post,'aPosition'),postScene=gl.getUniformLocation(post,'uScene'),postRes=gl.getUniformLocation(post,'uResolution'),postIntensity=gl.getUniformLocation(post,'uIntensity');
    let target=null;
    function releaseTarget(){if(target){gl.deleteFramebuffer(target.fbo);gl.deleteTexture(target.texture);gl.deleteRenderbuffer(target.depth);target=null;}}
    function resize(w,h){
      releaseTarget();const fbo=gl.createFramebuffer(),texture=gl.createTexture(),depth=gl.createRenderbuffer();
      gl.bindTexture(gl.TEXTURE_2D,texture);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,w,h,0,gl.RGBA,gl.UNSIGNED_BYTE,null);
      gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
      gl.bindRenderbuffer(gl.RENDERBUFFER,depth);gl.renderbufferStorage(gl.RENDERBUFFER,gl.DEPTH_COMPONENT16,w,h);
      gl.bindFramebuffer(gl.FRAMEBUFFER,fbo);gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_2D,texture,0);gl.framebufferRenderbuffer(gl.FRAMEBUFFER,gl.DEPTH_ATTACHMENT,gl.RENDERBUFFER,depth);
      if(gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE)throw Error('Incomplete spatial render target');
      target={fbo,texture,depth};gl.bindFramebuffer(gl.FRAMEBUFFER,null);
    }
    function bind(key,kind,alpha=0){
      const m=mesh[key];gl.bindBuffer(gl.ARRAY_BUFFER,m.buffer);
      gl.enableVertexAttribArray(pos);gl.vertexAttribPointer(pos,3,gl.FLOAT,false,32,0);
      gl.enableVertexAttribArray(normal);gl.vertexAttribPointer(normal,3,gl.FLOAT,false,32,12);
      gl.enableVertexAttribArray(uv);gl.vertexAttribPointer(uv,2,gl.FLOAT,false,32,24);
      gl.uniform1f(loc.uKind,kind);gl.uniform1f(loc.uShellAlpha,alpha);
      gl.drawArrays(key==='volume'?gl.POINTS:gl.TRIANGLES,0,m.count);
    }
    function render(state){
      if(!target||gl.isContextLost())return;
      const {time,variant,model,distance,intensity}=state,w=canvas.width,h=canvas.height;
      gl.bindFramebuffer(gl.FRAMEBUFFER,target.fbo);gl.viewport(0,0,w,h);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
      gl.useProgram(p);gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);gl.depthMask(true);
      gl.enable(gl.BLEND);gl.blendFuncSeparate(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA,gl.ONE,gl.ONE_MINUS_SRC_ALPHA);
      gl.uniformMatrix4fv(loc.uModel,false,model);gl.uniformMatrix4fv(loc.uViewProjection,false,perspective(w/h,distance));
      gl.uniform1f(loc.uTime,time);gl.uniform1f(loc.uScan,.97*Math.sin(time*TAU/8+.05));
      gl.uniform1f(loc.uDistance,distance);gl.uniform1f(loc.uPointScale,h*.062);gl.uniform1f(loc.uIntensity,intensity);
      if(variant==='volume'){gl.disable(gl.CULL_FACE);bind('volume',0);}
      else if(variant==='tomography'){
        gl.enable(gl.CULL_FACE);gl.cullFace(gl.FRONT);gl.depthMask(false);bind('box',1,.34);
        gl.disable(gl.CULL_FACE);gl.depthMask(true);bind('core',2);
        gl.depthMask(false);bind('plane',4);
        gl.enable(gl.CULL_FACE);gl.cullFace(gl.BACK);bind('box',1,.18);gl.disable(gl.CULL_FACE);
      }else{
        gl.enable(gl.CULL_FACE);gl.cullFace(gl.FRONT);bind('sheet',3);
        gl.cullFace(gl.BACK);bind('sheet',3);gl.disable(gl.CULL_FACE);
      }
      gl.depthMask(true);gl.disable(gl.DEPTH_TEST);gl.disable(gl.BLEND);
      gl.bindFramebuffer(gl.FRAMEBUFFER,null);gl.viewport(0,0,w,h);gl.useProgram(post);
      gl.bindBuffer(gl.ARRAY_BUFFER,quad);gl.disableVertexAttribArray(pos);gl.disableVertexAttribArray(normal);gl.disableVertexAttribArray(uv);
      gl.enableVertexAttribArray(postPos);gl.vertexAttribPointer(postPos,2,gl.FLOAT,false,8,0);
      gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,target.texture);gl.uniform1i(postScene,0);gl.uniform2f(postRes,w,h);gl.uniform1f(postIntensity,intensity);
      gl.drawArrays(gl.TRIANGLES,0,6);
    }
    return {name:'webgl',resize,render,destroy(){releaseTarget();Object.values(mesh).forEach(m=>gl.deleteBuffer(m.buffer));gl.deleteBuffer(quad);gl.deleteProgram(p);gl.deleteProgram(post);}};
  }

  // The fallback uses the same 3D parameterizations, camera and depth sorting. It is a
  // perspective renderer, not a pre-rendered image, and keeps drag / pause / export useful.
  function canvasRenderer(canvas) {
    const ctx=canvas.getContext('2d');if(!ctx)throw Error('No canvas rendering context');
    const coarse={box:cpuGeometry.box,core:parametric(corePoint,22,27),sheet:parametric(sheetPoint,35,24),plane:cpuGeometry.plane};
    const rgb=(a)=>`rgb(${a.map(v=>Math.round(clamp(v,0,255))).join(',')})`;
    function render(s){
      const w=canvas.width,h=canvas.height;ctx.clearRect(0,0,w,h);
      ctx.fillStyle='#09090d';ctx.fillRect(0,0,w,h);ctx.save();ctx.translate(w*.5,h*.5);ctx.scale(w/h,1);
      const bg=ctx.createRadialGradient(0,0,0,0,0,h*.48);bg.addColorStop(0,'#100d18');bg.addColorStop(1,'rgba(9,9,13,0)');ctx.fillStyle=bg;ctx.fillRect(-h*.5,-h*.5,h,h);ctx.restore();
      const f=h/(2*Math.tan(34*PI/360));
      function point(p){const q=transform(p,s.model),k=f/(s.distance-q[2]);return {x:w*.5+q[0]*k,y:h*.5-q[1]*k,z:q[2],k};}
      if(s.variant==='volume'){
        const data=cpuGeometry.volume,points=[];
        for(let i=0;i<data.length;i+=8){const p=[data[i]+.036*Math.sin(data[i+1]*3+s.time*.6),data[i+1],data[i+2]+.028*Math.cos(data[i+1]*3+s.time*.6)],q=point(p);points.push({p,q});}
        points.sort((a,b)=>a.q.z-b.q.z);
        for(const{p,q}of points){const band=Math.exp(-(((p[0]-1.65*Math.sin(s.time*1.15))/.19)**2)),l=.42+.48*(q.z+1.4)/2.8;
          ctx.fillStyle=rgb([105+band*99,83+band*77,142-band*54].map(v=>v*l));ctx.beginPath();ctx.arc(q.x,q.y,Math.max(.8,h*.029/(s.distance-q.z)),0,TAU);ctx.fill();}
        return;
      }
      const triangles=[];
      function add(data,kind){for(let i=0;i<data.length;i+=24){const vs=[];for(let k=0;k<3;k++){
        const o=i+k*8,u=data[o+6],v=data[o+7];let p=Array.from(data.subarray(o,o+3));
        if(kind===2)p=corePoint(u,v,s.time);if(kind===3)p=sheetPoint(u,v,s.time);if(kind===4)p[1]=.97*Math.sin(s.time*TAU/8+.05);
        vs.push({p,q:point(p)});}
        const n=norm(transform(norm(cross(sub(vs[1].p,vs[0].p),sub(vs[2].p,vs[0].p))),s.model));
        const light=.35+.65*Math.abs(n[0]*-.4+n[1]*.5+n[2]*.75),y=vs.reduce((a,v)=>a+v.p[1]/3,0),u=(data[i+6]+data[i+14]+data[i+22])/3;
        const band=kind===3?((.5+.5*Math.cos(u*8-s.time*.92))**15):Math.exp(-(((y-.97*Math.sin(s.time*TAU/8+.05))/.045)**2));
        const tint=kind===1?band*.22:band;
        const col=kind===4?[120,88,46]:(kind===2?[81+band*126,62+band*91,110-band*34]:[104+tint*115,82+tint*84,141-tint*45]).map(v=>v*light);
        triangles.push({vs,z:vs.reduce((a,v)=>a+v.q.z/3,0),color:rgb(col),alpha:kind===1?.19:kind===4?.065:.88});
      }}
      if(s.variant==='tomography'){add(coarse.box,1);add(coarse.core,2);add(coarse.plane,4);}else add(coarse.sheet,3);
      triangles.sort((a,b)=>a.z-b.z);
      for(const t of triangles){ctx.globalAlpha=t.alpha;ctx.fillStyle=t.color;ctx.beginPath();ctx.moveTo(t.vs[0].q.x,t.vs[0].q.y);t.vs.slice(1).forEach(v=>ctx.lineTo(v.q.x,v.q.y));ctx.closePath();ctx.fill();}
      ctx.globalAlpha=1;
    }
    return {name:'canvas-perspective',resize(){},render,destroy(){}};
  }

  function mount(canvas,options={}) {
    if(!(canvas instanceof HTMLCanvasElement))throw TypeError('SpatialMotion.mount needs a canvas');
    let variant=variants.has(options.variant)?options.variant:'tomography',intensity=clamp(Number(options.intensity??1),0,1.8);
    let time=0,paused=false,dead=false,frame=0,last=0,yaw=0,pitch=0,drag=null,width=0,height=0;
    let renderer=webGLRenderer(canvas)||canvasRenderer(canvas);
    canvas.dataset.renderer=renderer.name;canvas.dataset.variant=variant;canvas.style.touchAction='pan-y';
    function state(){
      const base=variant==='volume'?[.30,-.46,-.15]:variant==='tomography'?[.15,-.57,-.20]:[.24,-.18,-.18];
      const phase=time*TAU/8;
      const orbit=variant==='volume'?time*.23:variant==='tomography'?.16*Math.sin(phase):time*.14;
      const tilt=variant==='tomography'?.065*Math.sin(phase*2):.055*Math.sin(time*.46);
      const model=rotation(base[0]+pitch+tilt,base[1]+yaw+orbit,base[2]);
      // Frame by height on desktop and by width on narrow canvases; no object is cropped.
      const aspect=canvas.width/canvas.height,distance=Math.max(variant==='volume'?4.85:4.42,4.85/Math.max(aspect,1));
      return {time,variant,model,distance,intensity};
    }
    function draw(){if(!dead)renderer.render(state());}
    function resize(){
      if(dead)return;const box=canvas.getBoundingClientRect(),dpr=Math.min(window.devicePixelRatio||1,1.6);
      const w=Math.max(1,Math.round((box.width||700)*dpr)),h=Math.max(1,Math.round((box.height||250)*dpr));
      if(w===width&&h===height)return;width=w;height=h;canvas.width=w;canvas.height=h;renderer.resize(w,h);draw();
    }
    function tick(now){
      frame=0;if(dead||paused)return;
      if(last)time+=Math.min(.08,(now-last)/1000);last=now;draw();frame=requestAnimationFrame(tick);
    }
    function start(){last=0;if(!dead&&!paused&&!frame)frame=requestAnimationFrame(tick);}
    function stop(){if(frame)cancelAnimationFrame(frame);frame=0;last=0;}
    function pointerDown(e){if(e.button!==0)return;drag={id:e.pointerId,x:e.clientX,y:e.clientY,yaw,pitch};try{canvas.setPointerCapture?.(e.pointerId);}catch{}canvas.style.cursor='grabbing';}
    function pointerMove(e){if(!drag||e.pointerId!==drag.id)return;yaw=drag.yaw+(e.clientX-drag.x)*.007;pitch=clamp(drag.pitch+(e.clientY-drag.y)*.006,-1.0,1.0);draw();}
    function pointerUp(e){if(drag?.id!==e.pointerId)return;drag=null;canvas.style.cursor='grab';if(canvas.hasPointerCapture?.(e.pointerId))canvas.releasePointerCapture(e.pointerId);}
    function keyDown(e){
      const steps={ArrowLeft:[-.13,0],ArrowRight:[.13,0],ArrowUp:[0,-.10],ArrowDown:[0,.10]};
      if(steps[e.key]){e.preventDefault();yaw+=steps[e.key][0];pitch=clamp(pitch+steps[e.key][1],-1,1);draw();}
    }
    function lost(e){e.preventDefault();stop();canvas.dataset.rendererState='context-lost';}
    function restored(){if(dead)return;renderer.destroy();renderer=webGLRenderer(canvas)||canvasRenderer(canvas);canvas.dataset.renderer=renderer.name;canvas.dataset.rendererState='ready';width=0;height=0;resize();start();}
    canvas.style.cursor='grab';canvas.addEventListener('pointerdown',pointerDown);canvas.addEventListener('pointermove',pointerMove);
    canvas.addEventListener('pointerup',pointerUp);canvas.addEventListener('pointercancel',pointerUp);canvas.addEventListener('keydown',keyDown);canvas.addEventListener('webglcontextlost',lost);canvas.addEventListener('webglcontextrestored',restored);
    const observer=typeof ResizeObserver==='function'?new ResizeObserver(resize):null;observer?.observe(canvas);window.addEventListener('resize',resize);
    resize();draw();start();
    return {
      setPaused(value){paused=Boolean(value);if(paused){stop();draw();}else start();},
      reset(){time=0;yaw=0;pitch=0;last=0;draw();},
      setVariant(value){if(!variants.has(value))throw RangeError('Unknown spatial variant');variant=value;canvas.dataset.variant=value;time=0;yaw=0;pitch=0;last=0;draw();},
      renderAt(seconds){const s=Number(seconds);if(!Number.isFinite(s)||s<0)throw RangeError('renderAt needs finite nonnegative seconds');time=s;last=0;draw();},
      getState(){return {variant,time,paused,renderer:renderer.name,width:canvas.width,height:canvas.height,yaw,pitch};},
      destroy(){if(dead)return;dead=true;stop();observer?.disconnect();window.removeEventListener('resize',resize);
        canvas.removeEventListener('pointerdown',pointerDown);canvas.removeEventListener('pointermove',pointerMove);canvas.removeEventListener('pointerup',pointerUp);canvas.removeEventListener('pointercancel',pointerUp);canvas.removeEventListener('keydown',keyDown);canvas.removeEventListener('webglcontextlost',lost);canvas.removeEventListener('webglcontextrestored',restored);renderer.destroy();}
    };
  }
  window.SpatialMotion=Object.freeze({mount});
})();
