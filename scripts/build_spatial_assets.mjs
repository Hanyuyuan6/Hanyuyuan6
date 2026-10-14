#!/usr/bin/env node
/**
 * Deterministic Optical Monolith assets for a GitHub profile.
 *
 * Requires Node.js 20+, Playwright Chromium, img2webp and webpmux (libwebp).
 * Supply the openly licensed Noto Sans Regular/Bold TTFs with --fonts DIR.
 * npm install playwright && npx playwright install chromium
 * node scripts/build_spatial_assets.mjs --fonts /path/to/NotoSans
 *
 * --playwright /path/to/playwright/index.mjs can use an existing local install.
 * No browser account, remote page, telemetry, network font or remote asset is used.
 * Source geometry is conceptual artwork, not a measurement or scientific result.
 */
import { readFileSync, writeFileSync, mkdirSync, mkdtempSync, rmSync, statSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT=resolve(dirname(fileURLToPath(import.meta.url)),'..'),OUT=join(ROOT,'assets');
const args=process.argv.slice(2),option=name=>{const i=args.indexOf(name);return i<0?null:args[i+1];};
const fontDir=option('--fonts');
if(!fontDir)throw Error('Pass --fonts DIR containing NotoSans-Regular.ttf and NotoSans-Bold.ttf.');
const playwrightPath=option('--playwright'),img2webp=option('--img2webp')||'img2webp',webpmux=option('--webpmux')||'webpmux';
const {chromium}=playwrightPath?await import(pathToFileURL(resolve(playwrightPath)).href):await import('playwright');
const FPS=20,FRAMES=160,DURATION=8000;
const rendererFile=join(ROOT,'scripts/spatial-motion.js'),displayFile=join(ROOT,'data/profile-display.json');
const rendererSource=readFileSync(rendererFile,'utf8'),display=JSON.parse(readFileSync(displayFile,'utf8')),profile=display.profile;
const fonts=['Regular','Bold'].map(weight=>({weight:weight==='Bold'?'700':'400',name:`NotoSans-${weight}.ttf`,bytes:readFileSync(join(resolve(fontDir),`NotoSans-${weight}.ttf`))}));
const sha=value=>createHash('sha256').update(value).digest('hex');
const papers=Object.fromEntries(profile.projects.map(p=>[p.id,p]));
const cards=[
  {slug:'stsf-tpls',title:'STSF-TPLS',kind:'Paper + code',project:'lift',language:'PyTorch',phase:0},
  {slug:'remote-gpu-trainer',title:profile.tool.name,kind:'Open-source tool',language:'Python',phase:1.35},
  {slug:'shsi',title:'SHSI',kind:'Paper + code',project:'shsi',language:'MATLAB',phase:3.1},
  {slug:'ldgi',title:'LDGI',kind:'Paper + code',project:'loop',language:'MATLAB',phase:5.3}
].map(card=>({...card,venue:card.project?`${papers[card.project].venue} ${papers[card.project].year}`:'Agent skill',
  href:card.project?papers[card.project].code_url:profile.tool.url}));
const specs=[
  {name:'hero-monolith',width:1280,height:416,sceneWidth:640,sceneX:640,phase:0,quality:78,limit:Math.round(1.2*1024*1024),
    title:`${profile.person.name}. ${profile.narrative.field}. ${profile.person.position}, ${profile.person.institution}.`},
  ...cards.map(card=>({name:`card-${card.slug}-monolith`,width:640,height:240,sceneWidth:216,sceneX:424,quality:76,limit:700*1024,...card}))
];
mkdirSync(OUT,{recursive:true});
const work=mkdtempSync(join(tmpdir(),'github-monolith-build-'));
const browser=await chromium.launch({headless:true,args:['--enable-webgl','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const manifest={version:1,concept:'Optical Monolith',description:'Synthetic three-dimensional concept artwork; no measured data or research results.',
  period_ms:DURATION,fps:FPS,source:{
    'scripts/build_spatial_assets.mjs':sha(readFileSync(fileURLToPath(import.meta.url))),
    'scripts/spatial-motion.js':sha(rendererSource),'data/profile-display.json':sha(readFileSync(displayFile)),
    fonts:Object.fromEntries(fonts.map(f=>[f.name,sha(f.bytes)]))
  },assets:[]};

function webpInfo(file){
  const raw=execFileSync(webpmux,['-info',file],{encoding:'utf8'});
  const size=/Canvas size:\s*(\d+)\s*x\s*(\d+)/.exec(raw),frames=/Number of frames:\s*(\d+)/.exec(raw),loop=/Loop Count\s*:\s*(\d+)/.exec(raw);
  if(!size||!frames||!loop)throw Error(`Cannot read animated WebP metadata: ${raw}`);
  return {width:Number(size[1]),height:Number(size[2]),frames:Number(frames[1]),loop:Number(loop[1])};
}

try{
  for(const spec of specs){
    const folder=join(work,spec.name);mkdirSync(folder);
    const page=await browser.newPage({viewport:{width:spec.width,height:spec.height},deviceScaleFactor:1,reducedMotion:'reduce'});
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.setContent(`<html><body style="margin:0;background:#09090d"><canvas id="scene" style="position:absolute;left:-2000px;width:${spec.sceneWidth}px;height:${spec.height}px"></canvas><canvas id="output" width="${spec.width}" height="${spec.height}"></canvas></body></html>`);
    await page.addScriptTag({content:rendererSource});
    await page.evaluate(async({spec,profile,fonts})=>{
      for(const font of fonts){const face=new FontFace('Noto Sans Export',`url(data:font/ttf;base64,${font.data})`,{weight:font.weight});await face.load();document.fonts.add(face);}
      await document.fonts.ready;
      const scene=document.getElementById('scene'),output=document.getElementById('output'),ctx=output.getContext('2d');
      const model=SpatialMotion.mount(scene,{variant:'tomography',intensity:1});model.setPaused(true);
      const ink='#f3efff',muted='#a9a1bd',gold='#c8a66b';
      function font(size,bold=false){ctx.font=`${bold?'700':'400'} ${size}px "Noto Sans Export"`;ctx.letterSpacing='0px';}
      function line(text,x,y,size,color,bold=false,maxWidth=null){font(size,bold);if(maxWidth&&ctx.measureText(text).width>maxWidth)throw Error(`Text exceeds layout: ${text}`);ctx.fillStyle=color;ctx.fillText(text,x,y);}
      function drawType(){
        if(spec.name==='hero-monolith'){
          line(profile.person.name,64,151,76,ink,true,552);
          const split=profile.narrative.field.indexOf(' & ');
          const rows=split>=0?[profile.narrative.field.slice(0,split),profile.narrative.field.slice(split+1)]:[profile.narrative.field];
          rows.forEach((text,i)=>line(text,67,211+i*38,28,ink,false,540));
          ctx.fillStyle=gold;ctx.fillRect(68,282,38,1.5);
          line(profile.person.position,67,327,23,muted,false,540);
          line(profile.person.institution,67,361,23,muted,false,540);
        }else{
          font(14,true);ctx.letterSpacing='1.7px';ctx.fillStyle=muted;ctx.fillText(spec.kind.toUpperCase(),32,40);ctx.letterSpacing='0px';
          let size=44;while(size>34){font(size,true);if(ctx.measureText(spec.title).width<=370)break;size--;}
          line(spec.title,31,102,size,ink,true,374);
          line(spec.venue,32,153,23,ink,false,374);
          line(spec.language,32,191,19,muted,false,374);
          ctx.fillStyle=gold;ctx.fillRect(33,211,28,1.5);
        }
      }
      window.__renderFrame=time=>{
        // Canonical periodic time also makes offset phases bit-identical at loop boundaries.
        const periodic=Math.round(((time+spec.phase)%8)*1e6)/1e6;
        model.renderAt(periodic===8?0:periodic);
        ctx.clearRect(0,0,spec.width,spec.height);ctx.fillStyle='#09090d';ctx.fillRect(0,0,spec.width,spec.height);
        ctx.drawImage(scene,spec.sceneX,0,spec.sceneWidth,spec.height);drawType();
        ctx.strokeStyle='#2c2536';ctx.lineWidth=1;ctx.beginPath();ctx.roundRect(.5,.5,spec.width-1,spec.height-1,11);ctx.stroke();
        return output.toDataURL('image/png').split(',')[1];
      };
      window.__pixels=()=>Array.from(ctx.getImageData(0,0,spec.sceneX-12,spec.height).data);
      window.__destroy=()=>model.destroy();
    },{spec,profile,fonts:fonts.map(f=>({weight:f.weight,data:f.bytes.toString('base64')}))});

    const snapshots=new Map();
    for(let index=0;index<FRAMES;index++){
      const png=Buffer.from(await page.evaluate(t=>window.__renderFrame(t),index/FPS),'base64');
      writeFileSync(join(folder,`${String(index).padStart(3,'0')}.png`),png);
      if(index===0)writeFileSync(join(OUT,`${spec.name}-still.png`),png);
      if([0,20,80,159].includes(index))snapshots.set(index,sha(png));
      if(index%40===0)console.log(`${spec.name}: rendered ${index}/${FRAMES}`);
    }
    const endpoint=Buffer.from(await page.evaluate(()=>window.__renderFrame(8)),'base64');
    const first=readFileSync(join(folder,'000.png'));
    if(!first.equals(endpoint))throw Error(`${spec.name}: the 0/8 s loop endpoints differ`);
    const text0=await page.evaluate(()=>{window.__renderFrame(0);return window.__pixels();});
    const longTime={};
    for(const seconds of [1,10,20]){
      const png=Buffer.from(await page.evaluate(t=>window.__renderFrame(t),seconds),'base64');
      longTime[seconds]=sha(png);const text=await page.evaluate(()=>window.__pixels());
      if(text.some((value,index)=>value!==text0[index]))throw Error(`${spec.name}: stationary typography changes at ${seconds}s`);
    }
    if(new Set(snapshots.values()).size!==4||Object.values(longTime).some(value=>value===sha(first)))throw Error(`${spec.name}: expected visible continuing motion`);
    if(errors.length)throw Error(`${spec.name}: ${errors.join('; ')}`);
    await page.evaluate(()=>window.__destroy());await page.close();

    const target=join(OUT,`${spec.name}.webp`),frameFiles=Array.from({length:FRAMES},(_,i)=>join(folder,`${String(i).padStart(3,'0')}.png`));
    execFileSync(img2webp,['-loop','0','-min_size','-lossy','-q',String(spec.quality),'-m','6','-d',String(1000/FPS),...frameFiles,'-o',target],{stdio:['ignore','ignore','pipe']});
    const info=webpInfo(target),bytes=statSync(target).size;
    if(info.width!==spec.width||info.height!==spec.height||info.frames!==FRAMES||info.loop!==0)throw Error(`${spec.name}: delivered metadata mismatch`);
    if(bytes>spec.limit)throw Error(`${spec.name}: ${bytes} bytes exceeds size target ${spec.limit}`);
    manifest.assets.push({file:`assets/${spec.name}.webp`,format:'WebP',...info,fps:FPS,duration_ms:DURATION,bytes,sha256:sha(readFileSync(target)),
      still:{file:`assets/${spec.name}-still.png`,format:'PNG',width:spec.width,height:spec.height,frames:1,bytes:statSync(join(OUT,`${spec.name}-still.png`)).size,sha256:sha(first)},
      phase_offset_seconds:spec.phase,quality:spec.quality,title:spec.title,...(spec.venue?{venue:spec.venue,language:spec.language,link:spec.href}:{}),
      verification:{source_loop_endpoint_exact:true,static_type_exact_at_seconds:[1,10,20],source_sample_frames_distinct:4,source_motion_sha256:longTime}});
    console.log(`${spec.name}: ${bytes.toLocaleString()} bytes; ${FRAMES} frames; exact 8s loop`);
  }
  writeFileSync(join(OUT,'asset-manifest.json'),JSON.stringify(manifest,null,2)+'\n');
  console.log('Built five animations, five static PNGs and assets/asset-manifest.json.');
}finally{
  await browser.close();rmSync(work,{recursive:true,force:true});
}
