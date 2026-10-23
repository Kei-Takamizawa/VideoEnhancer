// Minimal WebView2 baseline using the product's HTMLVideoElement + controls.
const video=document.createElement('video');
video.id='video';video.controls=true;video.muted=true;
Object.assign(video.style,{position:'absolute',width:'100%',height:'100%',objectFit:'contain',background:'black'});
document.body.prepend(video);window.video=video;
window.htmlMetrics=()=>{const q=video.getVideoPlaybackQuality();return {time:video.currentTime,duration:video.duration,paused:video.paused,error:video.error?.code,quality:{dropped:q.droppedVideoFrames,total:q.totalVideoFrames,corrupted:q.corruptedVideoFrames},width:video.videoWidth,height:video.videoHeight};};
window.htmlBench=async(id,action,value)=>{
 const started=performance.now();let timeout;
 try {
  const frame=new Promise((resolve,reject)=>{
   timeout=setTimeout(()=>reject(Error('video presentation timeout')),15000);
   const ready=()=>video.requestVideoFrameCallback((now,metadata)=>resolve({now,metadata}));
   if(action==='load')video.addEventListener('loadeddata',ready,{once:true});
   else if(action==='seek'||action==='step')video.addEventListener('seeked',ready,{once:true});
   else ready();
   video.addEventListener('error',()=>reject(Error('MediaError '+video.error?.code)),{once:true});
  });
  if(action==='load'){video.src=value;video.load();await video.play();}
  else if(action==='seek'){video.currentTime=value;}
  else if(action==='step'){video.pause();video.currentTime=Math.max(0,video.currentTime+value);}
  const presented=await frame;clearTimeout(timeout);
  send({test_result:id,result:{latency_ms:performance.now()-started,presented,...htmlMetrics()}});
 }catch(e){clearTimeout(timeout);send({test_result:id,error:String(e),...htmlMetrics()});}
};
window.addEventListener('keydown',e=>{if(e.code==='Space'){e.preventDefault();video.paused?video.play():video.pause();}});
