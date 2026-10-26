/* Served as plain JavaScript by the generated static site. */
(() => {
  const root=document.getElementById('channel-now');if(!root)return;
  let state=JSON.parse(document.getElementById('channel-data').textContent);
  const $=id=>document.getElementById(id),videoId=/^[\w-]{11}$/,make=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!=null)n.textContent=text;return n;};
  function valid(v){return v&&videoId.test(v.id)&&typeof v.title==='string';}
  function date(value){if(!value)return'';const d=new Date(value);return Number.isNaN(+d)?'':d.toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'});}
  function render(next){state=next;const fresh=next.checkedAt&&Date.now()-Date.parse(next.checkedAt)<15*60000,live=fresh&&next.status==='live'&&valid(next.live),selected=live?next.live:next.latestStream;
    $('channel-status').textContent=live?'LIVE NOW':fresh&&next.status==='offline'?'LATEST STREAM':'LIVE / LATEST';root.classList.toggle('is-live',!!live);
    $('channel-title').textContent=live?'Join the live workshop.':'Catch up with Jason.';
    $('stream-title').textContent=valid(selected)?selected.title:'Game development, AI, and the next live build';
    $('stream-meta').textContent=live?'Streaming now on YouTube':valid(selected)?[selected.durationLabel,selected.published?date(selected.published):selected.byline].filter(Boolean).join(' · '):'Watch the channel for the next stream.';
    const watch=$('stream-watch');watch.href=valid(selected)?'https://www.youtube.com/watch?v='+selected.id:'https://www.youtube.com/@Unity3dCollege/live';watch.textContent=live?'Watch live on YouTube ↗':'Watch replay on YouTube ↗';
    const stage=$('channel-player');if(!stage.querySelector('iframe')&&valid(selected)){stage.replaceChildren();const play=make('button','stream-preview'),img=make('img');img.src='https://i.ytimg.com/vi/'+selected.id+'/hqdefault.jpg';img.alt='';img.loading='lazy';play.type='button';play.setAttribute('aria-label','Play '+selected.title);play.append(img,make('span','',live?'▶ Play live stream':'▶ Play latest stream'));play.addEventListener('click',()=>{const frame=make('iframe');frame.src='https://www.youtube-nocookie.com/embed/'+selected.id+'?autoplay=1';frame.title=selected.title;frame.allow='autoplay; encrypted-media; picture-in-picture';frame.allowFullscreen=true;stage.replaceChildren(frame);});stage.append(play);}
    // A refresh never interrupts a video the visitor has chosen to play.
    const list=$('channel-uploads');list.replaceChildren();for(const v of(next.uploads||[]).filter(valid).slice(0,5)){const li=make('li'),a=make('a'),img=make('img'),text=make('span');a.href='https://www.youtube.com/watch?v='+v.id;img.src='https://i.ytimg.com/vi/'+v.id+'/mqdefault.jpg';img.alt='';img.loading='lazy';text.append(make('b','',v.title),make('small','',date(v.published)));a.append(img,text);li.append(a);list.append(li);}
    $('channel-updated').textContent=next.checkedAt?'Channel checked '+new Date(next.checkedAt).toLocaleString()+ (next.refreshUnavailable?' · Live check temporarily unavailable.':''): 'Open YouTube for the current live status.';
  }
  async function refresh(){try{const r=await fetch('https://crew.gamedev.show/api/channel',{credentials:'omit',signal:AbortSignal.timeout(7000)});if(!r.ok)return;const d=await r.json();if(d.channelId!=='UCX_b3NNQN5bzExm-22-NVVg')return;render(d);}catch{if(Date.now()-Date.parse(state.checkedAt||0)>15*60000)render(state);}}
  render(state);refresh();setInterval(refresh,60000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
})();
