/* Baltigo Games: Portuguese presentation and measured game integration. */
(() => {
  'use strict';
  const gameInfo = window.__BALTIGO_GAME || {};
  const dictionary = window.__BALTIGO_PT || {};
  const normalize = value => String(value).replace(/\r/g, '').replace(/[ \t]+/g, ' ').trim();
  const exact = new Map(Object.entries(dictionary).map(([key, value]) => [normalize(key), value]));
  const folded = new Map(Object.entries(dictionary).map(([key, value]) => [normalize(key).toLowerCase(), value]));
  const labels = {
    Score:'Pontos', SCORE:'PONTOS', Target:'Meta', TARGET:'META', Level:'Nível', LEVEL:'NÍVEL',
    Lines:'Linhas', LINES:'LINHAS', Time:'Tempo', TIME:'TEMPO', Coins:'Moedas', COINS:'MOEDAS',
    Lives:'Vidas', LIVES:'VIDAS', Best:'Recorde', BEST:'RECORDE', Moves:'Jogadas', MOVE:'JOGADA',
    Kills:'Eliminações', Miss:'Erros', Missed:'Erros', Health:'Vida', Distance:'Distância',
    Position:'Posição', Shots:'Disparos', Power:'Força', Aim:'Mira', Money:'Dinheiro',
    Battery:'Bateria', Shield:'Escudo', Fill:'Ocupação', Collect:'Recolha', Keys:'Chaves',
    Points:'Pontos', Light:'Luz', Parts:'Peças', Alt:'Altura', Fuel:'Combustível',
    Solve:'Resolva', Row:'Tentativa', Wave:'Onda', Floor:'Andar', Charges:'Cargas',
    Hit:'Acertos', Shots:'Disparos', SHOTS:'DISPAROS', Shot:'Disparo', Bullets:'Munição',
    Enemies:'Inimigos', Mistakes:'Erros', Color:'Cor', COLOR:'COR', Dist:'Distância',
    Turn:'Vez', Bot:'Computador', CPU:'Computador', AI:'Computador', You:'Você',
    'Pictures Taken':'Fotos tiradas', 'Deactivating in':'Desativando em', 'Next Power-Up in':'Próximo bônus em',
    Passengers:'Passageiros', Stations:'Estações', Boarding:'Embarque', 'Doors Open':'Portas abertas',
    HP:'Vida', Vacc:'Vacinas', Live:'Vida', Energy:'Energia', Bonus:'Bônus', BONUS:'BÔNUS',
    Round:'Rodada', ROUND:'RODADA', Rounds:'Rodadas', 'Final score':'Pontuação final',
    Defend:'Defenda', Destroy:'Destrua', Red:'Vermelho', Green:'Verde', Blue:'Azul',
    Yellow:'Amarelo', Purple:'Roxo', Orange:'Laranja', RED:'VERMELHO', GREEN:'VERDE',
    BLUE:'AZUL', YELLOW:'AMARELO', PURPLE:'ROXO', ORANGE:'LARANJA',
    Control:'Controle', Controls:'Controles', Avoid:'Evite', Connect:'Conecte', Found:'Encontradas',
    Tap:'Toque', Hold:'Segure', Release:'Solte', Rotate:'Girar', Drop:'Soltar', Aligned:'Alinhado',
    Speed:'Velocidade', Timer:'Tempo', Seconds:'Segundos', SecondsLeft:'Segundos restantes',
    Clue:'Dica', Cores:'Núcleos', Shields:'Escudos', Stacked:'Empilhadas', Stars:'Estrelas',
    Slice:'Corte', Pop:'Estoure', Bullseyes:'Acertos no centro', Back:'Voltar',
    'Game Over':'Fim de jogo', 'GAME OVER':'FIM DE JOGO', 'How to Play':'Como jogar',
    PLAY:'JOGAR', Play:'Jogar', Start:'Jogar', START:'JOGAR', REPLAY:'JOGAR NOVAMENTE',
    Replay:'Jogar novamente', Restart:'Reiniciar', RESTART:'REINICIAR', Retry:'Tentar novamente',
    RETRY:'TENTAR NOVAMENTE', NEXT:'CONTINUAR', Next:'Continuar', Continue:'Continuar',
    Resume:'Continuar', Pause:'Pausar', PAUSED:'PAUSADO', MENU:'MENU', Menu:'Menu',
    Jump:'Saltar', JUMP:'SALTAR', Shoot:'Atirar', SHOOT:'ATIRAR', Attack:'Atacar',
    Action:'Ação', Punch:'Atacar', Hint:'Dica', Shuffle:'Misturar', Clear:'Limpar',
    Submit:'Confirmar', Enter:'Confirmar', Backspace:'Apagar', EXIT:'SAIR', Exit:'Sair',
    Easy:'Fácil', Medium:'Médio', Hard:'Difícil', Player:'Você', Computer:'Computador',
    White:'Brancas', Black:'Pretas', Draw:'Empate', Victory:'Vitória', Defeat:'Derrota',
    'Your Turn':'Sua vez', 'YOUR TURN':'SUA VEZ', 'AI Turn':'Vez do computador',
    'AI THINKING...':'COMPUTADOR JOGANDO...', 'You Win!':'Você venceu!', 'You Lose!':'Você perdeu!',
    'Time Left':'Tempo restante', 'Final Score':'Pontuação final', 'Your Score':'Seus pontos',
    'Best score':'Recorde', 'New Game':'Nova partida', 'Start Game':'Jogar',
    Popularity:'Popularidade', EgoSelf:'Ego', Chaos:'Caos', Reshuffle:'Misturar novamente',
    'Replay Level':'Repetir fase', 'Terrorists killed':'Inimigos eliminados',
  };
  if(gameInfo.slug==='shape-collector')Object.assign(labels,{
    CIRCLE:'CÍRCULO',SQUARE:'QUADRADO',TRIANGLE:'TRIÂNGULO',STAR:'ESTRELA',HEX:'HEXÁGONO',HEART:'CORAÇÃO',
  });
  if(gameInfo.slug==='unruly')Object.assign(labels,{
    Gold:'Ouro','Royal Ego':'Ego real','Problems Solved':'Problemas resolvidos',
  });
  const escaped = Object.keys(labels).sort((a,b)=>b.length-a.length).map(s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'));
  const labelLookup=Object.fromEntries(Object.entries(labels).map(([key,value])=>[key.toLowerCase(),value]));
  // Unicode boundaries are essential: ASCII \b sees the â in "Distância" as
  // a boundary after "Dist", repeatedly retranslating a MutationObserver node.
  const labelPattern = new RegExp('(^|[^\\p{L}\\p{M}\\p{N}_])(' + escaped.join('|') + ')(?=$|[^\\p{L}\\p{M}\\p{N}_])', 'giu');
  const state = window.__baltigo = {
    games: [], slug:gameInfo.slug, version:'20261025-7', translated:0, paused:false,
    status:'loading', score:null, outcome:null, untranslated:new Set(),
  };
  function cleanEmoji(value) {
    // These monochrome board symbols are actual chess/card pieces.
    if (/^[\s\u2654-\u265f\u2660-\u2667]+$/u.test(value)) return value;
    return value.replace(/\u23ec\ufe0f?/g,'⇓').replace(/\u26bd\ufe0f?/g,'Chutar')
      .replace(/\u25c0\ufe0f?/g,'←').replace(/\u25b6\ufe0f?/g,'→')
      .replace(/\u2b06\ufe0f?/g,'↑').replace(/\u2b07\ufe0f?/g,'↓')
      .replace(/[\p{Extended_Pictographic}\uFE0F\u200D]/gu,'');
  }
  const portugueseValues=new Set(Object.values(dictionary).map(value=>normalize(cleanEmoji(value)).toLowerCase()));
  function translate(value) {
    if (Array.isArray(value)) return value.map(translate);
    if (typeof value !== 'string') return value;
    const stripped = cleanEmoji(value).replace(/^(PONTOS|Pontos|VIDAS|Vidas|MOEDAS|Moedas|NÍVEL|Nível|META|Meta)(:?)[ \t]*(?=\d)/u,'$1$2 ');
    // DOM mutations may already contain server-translated text. Preserve those
    // phrases, including placeholders, rather than translating Portuguese verbs
    // such as "move" or "continue" as English UI labels for a second time.
    if(portugueseValues.has(normalize(stripped).toLowerCase()))return stripped;
    let result = dictionary[value] || exact.get(normalize(value)) || exact.get(normalize(stripped)) || folded.get(normalize(stripped).toLowerCase());
    if (!result) result = stripped.replace(labelPattern, (match,prefix,label)=>prefix+(labels[label]||labelLookup[label.toLowerCase()]));
    if (result !== value) state.translated += 1;
    return result;
  }
  state.translate = translate;
  const canvasLabels=new Set();
  state.canvasTexts=()=>[...canvasLabels];
  const send = (type, extra={}) => {
    if (window.parent !== window) window.parent.postMessage({type, slug:gameInfo.slug, ...extra}, location.origin);
  };
  let lastRoundConfirmation=0;let reloadingRound=false;let awaitingRoundInput=false;
  const roundStorageKey='baltigo:next-round:'+gameInfo.slug;
  const sourceReplayGames=new Set(['crowd-control','cut-rope','demon','gunman','perfect-square','road-cross','penalty','car-race','archer','ludo','chess','sudoku','crossy-road','curve-snake','memory','stack-tower','tetris','line-trap','swipe-assassin','level-devil']);
  const documentReplay=gameInfo.transitions?.replay_policy?gameInfo.transitions.replay_policy==='document':!sourceReplayGames.has(gameInfo.slug);
  try{awaitingRoundInput=sessionStorage.getItem(roundStorageKey)==='1';sessionStorage.removeItem(roundStorageKey);}catch{}
  let lastStartGesture=-Infinity;
  const startRound=()=>{awaitingRoundInput=false;state.status='playing';state.outcome=null;if(originalNow()-lastStartGesture>350){lastStartGesture=originalNow();send('baltigo:start');}};
  if(gameInfo.slug==='penalty')state.resumePenaltyRound=()=>{
    let remaining=40;
    const afterTransition=()=>{
      const active=state.games.flatMap(game=>game.scene?.getScenes(true)||[]);
      if(active.some(scene=>scene.sys.settings.key==='GameScene'&&scene.children?.list?.length)&&!active.some(scene=>/^(WinScene|GameOverScene)$/.test(scene.sys.settings.key))){
        report();startRound();return;
      }
      if(--remaining>0)originalTimeout(afterTransition,50);
    };
    originalTimeout(afterTransition,0);
  };
  const reloadRound=()=>{
    if(reloadingRound)return;
    reloadingRound=true;
    try{sessionStorage.setItem(roundStorageKey,'1');}catch{}
    for(const game of state.games)if(!game.pendingDestroy)game.destroy(true);
    originalTimeout(()=>{
      const url=new URL(location.href);url.searchParams.set('_baltigo_round',originalDateNow().toString(36));
      location.replace(url.href);
    },80);
  };
  state.completeAndRestart=(data={})=>{
    // sceneComplete is an actual source outcome, not evidence that another
    // authored level exists. A final screen stays visible until its user acts.
    const outcome=data.result==='win'?'win':data.result==='fail'||data.result==='lose'?'lose':'finished';
    send('baltigo:result',{score:Number.isFinite(data.score)?data.score:state.score,outcome});
    if(originalNow()-lastRoundConfirmation>1500||!lastRoundConfirmation||reloadingRound)return;
    // Reload the isolated document to reset constructors, listeners and clocks.
    // scene.restart() alone retained stale won/paused flags in several sources.
    reloadRound();
  };
  const confirmationLabel=object=>{
    const labels=[object.texture?.key,object.texture?.__baltigoLabel,object.text,...(object.list||[]).map(child=>child.text)].filter(Boolean);
    const bounds=object.frame!==null&&object.active!==false?object.getBounds?.():null;
    if(bounds&&object.scene&&bounds.width<=object.scene.scale.width*.7&&bounds.height<=object.scene.scale.height*.25){
      const visit=other=>{
        if(other.list)other.list.forEach(visit);
        if(other.scene&&other.active!==false&&typeof other.text==='string'&&other.text.length<45&&effectiveVisible(other)&&/^(jogar|reiniciar|replay|restart|retry|tentar novamente|repetir|nova partida|continuar|next)/i.test(other.text.trim())){
          const b=other.getBounds();if(bounds.contains(b.centerX,b.centerY))labels.push(other.text);
        }
      };
      object.scene.children?.list.forEach(visit);
    }
    return labels.join(' ');
  };
  const isRoundConfirmation=object=>object.__baltigoRoundConfirmation===true;
  const canvasFitStyle=document.createElement('style');
  canvasFitStyle.dataset.baltigoCanvasFit='true';
  canvasFitStyle.textContent='canvas[data-baltigo-flex-fit="true"]{margin:0!important}';
  if(gameInfo.slug==='archer')canvasFitStyle.textContent+='body{transform:none!important;width:100%!important;height:100%!important;position:static!important;top:auto!important;left:auto!important}';
  document.head.append(canvasFitStyle);
  function fitFlexCanvas(game){
    const canvas=game.canvas;const parent=canvas?.parentElement;if(!parent)return;
    const flex=/^(?:inline-)?flex$/.test(getComputedStyle(parent).display);
    const fitted=canvas.dataset.baltigoFlexFit==='true';
    if(flex&&!fitted){
      // Flexbox already centers this canvas. Phaser's CENTER_BOTH margins would
      // apply the same offset a second time, shifting both rendering and input.
      canvas.dataset.baltigoFlexFit='true';game.scale?.updateBounds();
    }else if(!flex&&fitted){
      delete canvas.dataset.baltigoFlexFit;game.scale?.refresh();
    }
  }
  // Keep the enclosing Telegram/browser player responsible for expansion.
  if(window.parent!==window) for(const method of ['requestFullscreen','webkitRequestFullscreen']) {
    if(typeof Element.prototype[method]!=='function')continue;
    Element.prototype[method]=function(){send('baltigo:fullscreen');return Promise.resolve();};
  }

  // Plain canvas games draw labels directly. Translate measurement and rendering
  // together so centered labels retain their intended alignment.
  const context = window.CanvasRenderingContext2D?.prototype;
  if (context) for (const method of ['fillText','strokeText','measureText']) {
    const original = context[method];
    context[method] = function(text,...args) {
      const translated=translate(text);
      if(method!=='measureText'&&typeof translated==='string'&&translated.trim()&&translated.length<=1000){
        canvasLabels.add(translated);
        if(canvasLabels.size>200)canvasLabels.delete(canvasLabels.values().next().value);
      }
      return original.call(this,translated,...args);
    };
  }

  const uiTextures = {
    htpbox:'Como jogar', ovrbox:'Fim de jogo', lvlbox:'Fase concluída',
    playbtn:'Jogar', play_btn:'Jogar', replay:'Jogar novamente',
    lvl_replay:'Repetir fase', next:'Continuar', restartbtn:'Reiniciar',
    htp:'Como jogar', howtoplay:'Como jogar', 'how-to-play':'Como jogar',
    gameovrbox:'Fim de jogo', play_game:'Jogar', playgame:'Jogar',
    play_button:'Jogar', playbutton:'Jogar', button_play:'Jogar', playbtn1:'Jogar', playbtnbg:'Jogar',
    playtbtn:'Jogar', replay_level:'Repetir fase', replaylevel:'Repetir fase',
    replay_button:'Jogar novamente', replay_button_big:'Jogar novamente',
    replay_button2:'Jogar novamente', replaybtn:'Jogar novamente',
    nextbtn:'Continuar', next_button:'Continuar', next_level_button:'Continuar',
    button_next:'Continuar', restart:'Reiniciar', restart1:'Reiniciar', restart1btn:'Reiniciar',
    button_retry:'Tentar novamente', retry:'Tentar novamente', retrybtn:'Tentar novamente', button_restart:'Reiniciar',
    lvlrestart:'Repetir fase', ovrrestart:'Reiniciar', ovrbtn:'Reiniciar',
    dialog_bg_start:'Como jogar', level_complete:'Fase concluída', game_over:'Fim de jogo',
  };
  if(gameInfo.slug==='candy-crush'){uiTextures.re='Misturar';uiTextures.reshuffle='Misturar';}
  if(documentReplay)for(const key of Object.keys(uiTextures))if(uiTextures[key]==='Continuar')uiTextures[key]='Nova partida';
  const uiKey=(key,image)=>{
    const direct=String(key).toLowerCase();if(uiTextures[direct])return direct;
    if(direct==='button'&&['abhita','antigravity','endless-mafia','endless-runner','fly-monkey','planet-visitor','devil-king'].includes(gameInfo.slug))return 'playbtn';
    const file=String(image?.src||'').split('/').pop().split('?')[0].replace(/\.[^.]+$/,'').toLowerCase();
    return uiTextures[file]?file:direct;
  };
  const isPanelKey=key=>/box$/.test(String(key).toLowerCase())||/^(htp|howtoplay|how-to-play|dialog_bg_start|level_complete|game_over)$/.test(String(key).toLowerCase());
  function localizedTexture(key, image) {
    const label = uiTextures[String(key).toLowerCase()];
    if (!label || !image || !(image.width>0 && image.height>0)) return image;
    const canvas = document.createElement('canvas'); canvas.width=image.width; canvas.height=image.height;
    const ctx = canvas.getContext('2d');
    const panel = isPanelKey(key);
    const pad = Math.max(2, Math.min(canvas.width,canvas.height)*.015);
    const radius = Math.min(canvas.width,canvas.height)*.025;
    const gradient = ctx.createLinearGradient(0,0,canvas.width,canvas.height);
    gradient.addColorStop(0,panel?'#202733':'#ff754b'); gradient.addColorStop(1,panel?'#111722':'#ff9867');
    ctx.fillStyle=gradient; ctx.beginPath(); ctx.roundRect(pad,pad,canvas.width-pad*2,canvas.height-pad*2,radius); ctx.fill();
    ctx.strokeStyle=panel?'#77d8d0':'#ffd2b7';ctx.lineWidth=Math.max(2,pad*.5);ctx.stroke();
    ctx.fillStyle=panel?'#f0f5ff':'#08251e';ctx.textAlign='center';ctx.textBaseline='middle';
    const size = panel ? Math.min(canvas.width*.066,canvas.height*.1) : Math.min(canvas.width*.075,canvas.height*.45);
    ctx.font=`700 ${size}px system-ui,Arial`;
    // Panel titles are actual scene text when the source already creates one.
    // A separately synchronized title is added only when the panel needs it.
    if(!panel)ctx.fillText(label,canvas.width/2,canvas.height/2,canvas.width*.92);
    return canvas;
  }
  function effectiveVisible(object){
    for(let current=object;current;current=current.parentContainer)if(current.visible===false||current.alpha===0)return false;
    return true;
  }
  function fontSize(object,size){
    if(Math.abs(parseFloat(object.style?.fontSize||0)-size)>.1)object.setFontSize(size);
    return object;
  }
  function panelTitle(image,label){
    if(image.__baltigoTitleAttached||!image.scene)return;
    image.__baltigoTitleAttached=true;const scene=image.scene;let header=null;
    const comparable=value=>normalize(value).toLowerCase().replace(/[!?.:]/g,'');
    const labels=label==='Como jogar'?['como jogar','instruções da missão']:label==='Fim de jogo'?['fim de jogo','você perdeu','tente novamente','tentar novamente']:['fase concluída','você venceu','missão concluída'];
    const children=()=>{const list=[];const visit=object=>{list.push(object);if(Array.isArray(object.list))object.list.forEach(visit);};(scene.children?.list||[]).forEach(visit);return list;};
    const update=()=>{
      if(!image.scene||!image.active){if(header)header.setVisible(false);return;}
      let bounds=image.getBounds();
      const fit=Math.min(1,scene.scale.width*.92/Math.max(1,bounds.width),scene.scale.height*.84/Math.max(1,bounds.height));
      if(fit<.999){image.setScale(image.scaleX*fit,image.scaleY*fit);bounds=image.getBounds();}
      const objects=children();
      const native=objects.some(object=>!object.__baltigoPanelHeader&&typeof object.text==='string'&&effectiveVisible(object)&&labels.some(label=>comparable(object.text)===label||comparable(object.text).startsWith(label+'\n'))&&bounds.contains(object.getBounds().centerX,object.getBounds().centerY));
      if(effectiveVisible(image))for(const object of objects){
        if(object.__baltigoPanelFitted||object.__baltigoPanelHeader||typeof object.text!=='string'||object.text.length<40||!effectiveVisible(object)||!object.setWordWrapWidth)continue;
        if(object.parentContainer!==image.parentContainer&&object.depth<image.depth)continue;
        const box=object.getBounds();if(!bounds.contains(box.centerX,box.centerY))continue;
        const parentMatrix=object.parentContainer?.getWorldTransformMatrix();
        const parentScale=parentMatrix?Math.hypot(parentMatrix.a,parentMatrix.b):1;
        object.setWordWrapWidth(Math.min(bounds.width*.86,scene.scale.width*.84)/Math.max(.01,parentScale*Math.abs(object.scaleX||1)));
        const updated=object.getBounds();
        if(updated.left<bounds.left+bounds.width*.04||updated.right>bounds.right-bounds.width*.04){
          const originX=bounds.centerX+(object.originX-.5)*updated.width;
          if(parentMatrix){const world=object.getWorldTransformMatrix();object.x=parentMatrix.applyInverse(originX,world.ty,{}).x;}
          else object.x=originX;
        }
        object.__baltigoPanelFitted=true;
      }
      if(native||!effectiveVisible(image)){if(header)header.setVisible(false);return;}
      if(!header){header=scene.add.text(0,0,label,{fontFamily:'Arial,sans-serif',fontStyle:'bold',color:'#f4f4f2',align:'center'}).setOrigin(.5,0).setDepth(100000);header.__baltigoPanelHeader=true;}
      const ratio=(scene.game.canvas.getBoundingClientRect().width||scene.game.scale.width)/scene.game.scale.width;
      fontSize(header,Math.max(42,14/Math.max(.05,ratio)));
      if(Math.abs((header.style.wordWrapWidth||0)-bounds.width*.88)>.1)header.setWordWrapWidth(bounds.width*.88);
      header.setPosition(bounds.centerX,bounds.top+Math.min(bounds.height*.075,65)).setVisible(true);
      const headerBottom=header.getBounds().bottom;
      for(const object of objects){
        if(!object.__baltigoPanelFitted||!effectiveVisible(object)||typeof object.text!=='string')continue;
        const box=object.getBounds();if(!bounds.contains(box.centerX,box.centerY))continue;
        const top=headerBottom+Math.max(20,8/Math.max(.05,ratio));
        const bottom=bounds.bottom-bounds.height*.06;
        if(box.top<top&&box.height<=bottom-top){
          const matrix=object.parentContainer?.getWorldTransformMatrix();
          if(matrix){const world=object.getWorldTransformMatrix();object.y=matrix.applyInverse(world.tx,world.ty+top-box.top,{}).y;}
          else object.y+=top-box.top;
        }
      }
    };
    scene.events.on('postupdate',update);
    image.once('destroy',()=>{scene.events.off('postupdate',update);header?.destroy();});
  }
  function patchPhaser(P) {
    if (!P || P.__baltigoPatched || !P.Game) return;
    P.__baltigoPatched=true;
    for (const object of [P.GameObjects?.Text,P.GameObjects?.BitmapText]) {
      if (!object?.prototype?.setText) continue;
      const original=object.prototype.setText;
      object.prototype.setText=function(value){return original.call(this,translate(value));};
    }
    const manager=P.Textures?.TextureManager?.prototype;
    if (manager?.addImage) {
      const original=manager.addImage;
      manager.addImage=function(key,image,...args){
        const labelKey=uiKey(key,image);
        const texture=original.call(this,key,localizedTexture(labelKey,image),...args);
        if(texture&&uiTextures[labelKey])texture.__baltigoLabel=uiTextures[labelKey];
        if(texture&&isPanelKey(labelKey))texture.__baltigoPanelLabel=uiTextures[labelKey];
        return texture;
      };
    }
    const imagePrototype=P.GameObjects?.Image?.prototype;
    if(imagePrototype?.setTexture){const original=imagePrototype.setTexture;imagePrototype.setTexture=function(...args){
      const known=uiKey(args[0]);
      if(uiTextures[known]&&this.scene?.textures&&!this.scene.textures.exists(args[0])){
        const panel=isPanelKey(known);
        const texture=this.scene.textures.addImage(args[0],localizedTexture(known,{width:panel?1800:400,height:panel?1400:124}));
        texture.__baltigoLabel=uiTextures[known];
        if(panel)texture.__baltigoPanelLabel=uiTextures[known];
      }
      // Abhita shipped no play_button.png. Its source still instantiated the
      // missing 'button' texture, leaving only a tiny checker as a start target.
      if(gameInfo.slug==='abhita'&&args[0]==='button'&&this.scene?.textures&&!this.scene.textures.exists('button'))this.scene.textures.addImage('button',localizedTexture('playbtn',{width:640,height:144})).__baltigoLabel='Jogar';
      const result=original.apply(this,args);if(this.texture?.__baltigoPanelLabel)panelTitle(this,this.texture.__baltigoPanelLabel);return result;
    };}
    const objectPrototype=P.GameObjects?.GameObject?.prototype;
    if(objectPrototype?.on){
      const original=objectPrototype.on;
      objectPrototype.on=function(event,callback,...args){
        if(/^pointer(?:down|up)$/.test(event)&&typeof callback==='function'&&/completeAndRestart/.test(Function.prototype.toString.call(callback))){
          this.__baltigoRoundConfirmation=true;
          if(typeof this.setText==='function')this.setText('Nova partida');
          else if(this.texture&&this.scene?.textures){
            const key='__baltigo_new_round_'+this.texture.key;
            if(!this.scene.textures.exists(key)){
              const source=this.texture.getSourceImage();
              uiTextures.new_round='Nova partida';
              const texture=this.scene.textures.addImage(key,localizedTexture('new_round',source));
              texture.__baltigoLabel='Nova partida';
            }
            this.setTexture(key);
          }
        }
        return original.call(this,event,callback,...args);
      };
    }
    if(objectPrototype?.emit){
      const original=objectPrototype.emit;
      objectPrototype.emit=function(event,...args){
        if(!/^pointer(?:down|up)$/.test(event)||!this.input?.enabled||this.active===false||!this.scene)return original.call(this,event,...args);
        const label=confirmationLabel(this);
        if(documentReplay&&/^pointer(?:down|up)$/.test(event)&&this.input?.enabled&&(/next|nova partida/i.test(label)||/^continuar$/i.test(label.trim())&&state.status==='finished')){
          for(const argument of args)if(typeof argument?.stopPropagation==='function')argument.stopPropagation();
          if(!reloadingRound)report();reloadRound();return true;
        }
        if(documentReplay&&/^pointer(?:down|up)$/.test(event)&&this.input?.enabled&&/replay|restart|retry|reiniciar|tentar novamente|repetir|jogar novamente/i.test(label)){
          // The single-round source constructors own state that scene.restart()
          // frequently leaves behind. An actual Replay gesture gets a clean
          // document; authored multi-phase campaigns retain their own replay.
          for(const argument of args)if(typeof argument?.stopPropagation==='function')argument.stopPropagation();
          if(!reloadingRound)report();reloadRound();return true;
        }
        if(/^pointer(?:down|up)$/.test(event)&&this.input?.enabled&&(isRoundConfirmation(this)||/next|nova partida/i.test(label)))lastRoundConfirmation=originalNow();
        else if(event==='pointerdown'&&this.input?.enabled&&/play|start|replay|next|jogar|reiniciar|continuar|repetir/i.test(label)){
          startRound();
        }
        return original.call(this,event,...args);
      };
    }
    const Original=P.Game;
    P.Game=new Proxy(Original,{construct(Target,args,newTarget){
      const game=Reflect.construct(Target,args,newTarget);
      state.games.push(game);
      game.events.once('ready',()=>{fitFlexCanvas(game);game.scale?.on('resize',()=>fitFlexCanvas(game));});
      return game;
    }});
  }
  let phaser=window.Phaser;
  if (phaser) patchPhaser(phaser);
  else Object.defineProperty(window,'Phaser',{configurable:true,enumerable:true,get(){return phaser;},set(value){phaser=value;patchPhaser(value);}});

  function allObjects() {
    const results=[];
    const visit=(object,scene)=>{
      if(!object)return;
      results.push({object,scene});
      if(Array.isArray(object.list)) object.list.forEach(child=>visit(child,scene));
    };
    for(const game of state.games) for(const scene of game.scene?.scenes||[]) {
      if(scene.sys?.isActive()) for(const object of scene.children?.list||[]) visit(object,scene);
    }
    return results;
  }
  function fitResultBackdrop(scene){
    if(scene.__baltigoBackdropChecked||!/^(MainMenuScene|WinScene|GameOverScene|LoseScene|VictoryScene|ResultScene)$/.test(scene.sys.settings.key))return;
    scene.__baltigoBackdropChecked=true;
    const width=scene.scale.width,height=scene.scale.height;
    const full=scene.children.list.some(object=>{if(object.type!=='Image'&&object.type!=='TileSprite')return false;const b=object.getBounds();return b.width>=width*.9&&b.height>=height*.9;});
    if(!full){
      const key=['background','bg','demon_slayer_background','winbg','ovrbg'].find(key=>scene.textures.exists(key));
      if(key){scene.add.image(width/2,height/2,key).setDisplaySize(width,height).setDepth(-1000).setScrollFactor(0);scene.add.rectangle(width/2,height/2,width,height,0x081124,.4).setDepth(-999).setScrollFactor(0);}
    }
    const fit=()=>{
      const ratio=scene.game.canvas.getBoundingClientRect().width/width;
      if(!(ratio>0))return;
      const visit=object=>{
        if(object.list)object.list.forEach(visit);
        if(typeof object.text!=='string'||object.text.length<12||!object.setFontSize||!effectiveVisible(object)||object.__baltigoPanelHeader)return;
        const matrix=object.parentContainer?.getWorldTransformMatrix();
        const scale=(matrix?Math.hypot(matrix.a,matrix.b):1)*Math.abs(object.scaleX||1)*(scene.cameras.main.zoom||1);
        const minimum=14/Math.max(.01,ratio*scale);
        if(parseFloat(object.style?.fontSize||object.fontSize||0)<minimum)fontSize(object,minimum);
        if(object.setWordWrapWidth){
          const maximum=width*.84/Math.max(.01,scale);
          if(object.width>maximum||object.style?.wordWrapWidth>maximum)object.setWordWrapWidth(maximum);
        }
      };
      scene.children.list.forEach(visit);
    };
    scene.events.on('postupdate',fit);fit();
    scene.events.once('shutdown',()=>{delete scene.__baltigoBackdropChecked;scene.events.off('postupdate',fit);});
  }
  function fitTerminalConfirmation(scene){
    if(gameInfo.slug!=='window-shooter'||!/^(GameOver|LevelComplete)$/.test(scene.sys.settings.key)||scene.__baltigoTerminalButton)return;
    scene.__baltigoTerminalButton=true;
    const ratio=scene.game.canvas.getBoundingClientRect().width/scene.scale.width;
    const width=Math.min(scene.scale.width*.8,300/Math.max(.05,ratio));
    const height=Math.max(124,48/Math.max(.05,ratio));
    const x=scene.scale.width/2,y=scene.scale.height*.78;
    const button=scene.add.rectangle(x,y,width,height,0xff885b).setStrokeStyle(3,0xffd2b7).setDepth(10000).setInteractive({useHandCursor:true});
    button.name='__baltigo_replay';
    scene.add.text(x,y,'Jogar novamente',{fontFamily:'Arial,sans-serif',fontSize:Math.max(40,16/Math.max(.05,ratio)),fontStyle:'bold',color:'#102429'}).setOrigin(.5).setDepth(10001);
    button.on('pointerdown',reloadRound);
    scene.events.once('shutdown',()=>{delete scene.__baltigoTerminalButton;});
  }
  function fitGamePresentation(scene){
    if(scene.__baltigoPresentation||!['buttermilk','fruit-cosmics','demon','candy-crush'].includes(gameInfo.slug))return;
    scene.__baltigoPresentation=true;
    const update=()=>{
      const ratio=scene.game.canvas.getBoundingClientRect().width/scene.scale.width;
      if(!(ratio>0))return;
      if(gameInfo.slug==='buttermilk'&&scene.scorePill&&scene.timerPill&&scene.scoreValueText&&scene.timerValueText){
        const label=scene.children.list.find(o=>o!==scene.scoreValueText&&typeof o.text==='string'&&/^PONTOS\s*:/.test(o.text));
        const timerLabel=scene.children.list.find(o=>o!==scene.timerValueText&&typeof o.text==='string'&&/^TEMPO\s*:/.test(o.text));
        const small=Math.max(34,12/ratio),large=Math.max(44,16/ratio);
        scene.scorePill.setDisplaySize(400,124);scene.timerPill.setDisplaySize(400,124);
        for(const [pill,title,value]of [[scene.scorePill,label,scene.scoreValueText],[scene.timerPill,timerLabel,scene.timerValueText]]){
          if(!title)continue;
          const left=pill.originX===1?pill.x-400:pill.x;
          title.setOrigin(0,0).setPosition(left+62,pill.y+8);fontSize(title,small);
          value.setOrigin(0,0).setPosition(left+62,pill.y+52);fontSize(value,large);
        }
      }
      if(gameInfo.slug==='fruit-cosmics'&&scene.scoreText&&scene.timerText&&scene.livesText){
        if(!scene.__baltigoHud){
          for(const object of scene.children.list)if(object.y<160&&/^(scoreback|stopwatchIcon)$/.test(object.texture?.key||''))object.setVisible(false);
          scene.__baltigoHud=scene.add.graphics().setDepth(10).setScrollFactor(0);
          scene.__baltigoHud.fillStyle(0x111d31,.94).fillRoundedRect(20,18,scene.scale.width-40,140,22);
          scene.__baltigoHud.lineStyle(2,0x77d8d0,.65).strokeRoundedRect(20,18,scene.scale.width-40,140,22);
        }
        for(const [index,object,label]of [[0,scene.scoreText,'PONTOS'],[1,scene.timerText,'TEMPO'],[2,scene.livesText,'VIDAS']]){
          const value=String(object.text).replace(/^[^\d-]*/,'').trim();
          const text=label+'\n'+value;
          if(object.text!==text)object.setText(text);
          object.setOrigin(.5,0).setPosition(scene.scale.width*(index+.5)/3,30);fontSize(object,Math.max(42,15/ratio));
          if(object.style.color!=='#f4f7ff')object.setColor('#f4f7ff');
          if(object.style.strokeThickness)object.setStroke('#000000',0);
          if(object.style.align!=='center')object.setAlign('center');
          const max=scene.scale.width/3-36;
          if(object.width>max)fontSize(object,parseFloat(object.style.fontSize)*max/object.width);
        }
      }
      if(gameInfo.slug==='demon'){
        for(const object of [scene.scoreText,scene.floorText,scene.hpText,scene.timerText])if(object?.active)fontSize(object,Math.max(40,14/ratio));
        if(scene.hpText)scene.hpText.y=84;
        if(scene.nextFloorHint?.active)fontSize(scene.nextFloorHint,Math.max(40,14/ratio));
      }
      if(gameInfo.slug==='candy-crush'&&scene.scoreText?.active){
        const texts=scene.children.list.filter(object=>object.active&&typeof object.text==='string'&&object.y<200);
        const scoreLabel=texts.find(object=>/^PONTOS\s*:?\s*$/i.test(object.text));
        const levelLabel=texts.find(object=>/^N[ÍI]VEL\s*:?\s*$/i.test(object.text));
        const timeLabel=texts.find(object=>/^TEMPO\s*:?\s*$/i.test(object.text));
        const timeValue=texts.find(object=>/^\d{2}:\d{2}$/.test(object.text));
        const levelValue=texts.find(object=>object!==scene.scoreText&&/^\d+$/.test(object.text)&&object.x>scene.scale.width*.3&&object.x<scene.scale.width*.7);
        if(scoreLabel&&levelLabel&&timeLabel&&timeValue&&levelValue){
          if(!scene.__baltigoCandyHud){
            for(const object of scene.children.list)if(object.y<200&&/^(scorebg|timebg|lvltxtbg)$/.test(object.texture?.key||''))object.setVisible(false);
            const width=scene.scale.width;
            const hud=scene.__baltigoCandyHud=scene.add.graphics().setDepth(2).setScrollFactor(0);
            hud.fillStyle(0x111d31,.96).fillRoundedRect(20,18,width-40,164,18);
            hud.lineStyle(2,0x77d8d0,.65).strokeRoundedRect(20,18,width-40,164,18);
            hud.lineStyle(2,0x31445c,.9);
            for(const x of [width/3,width*2/3])hud.lineBetween(x,38,x,162);
          }
          for(const [index,label,value,title]of [[0,scoreLabel,scene.scoreText,'PONTOS'],[1,levelLabel,levelValue,'NÍVEL'],[2,timeLabel,timeValue,'TEMPO']]){
            const x=scene.scale.width*(index+.5)/3;
            if(label.text!==title)label.setText(title);
            label.setOrigin(.5,0).setPosition(x,36);value.setOrigin(.5,0).setPosition(x,94);
            fontSize(label,Math.max(40,14/ratio));fontSize(value,Math.max(48,16/ratio));
            for(const object of [label,value])if(object.style.color!=='#f4f7ff')object.setColor('#f4f7ff');
          }
        }
      }
    };
    scene.events.on('postupdate',update);
    scene.events.once('shutdown',()=>{scene.events.off('postupdate',update);delete scene.__baltigoPresentation;delete scene.__baltigoHud;delete scene.__baltigoCandyHud;});
    update();
  }
  state.texts=()=>allObjects().filter(({object})=>typeof object.text==='string').map(({object,scene})=>({text:object.text,x:object.x,y:object.y,scene:scene.sys.settings.key,visible:object.visible}));
  state.visibleText=()=>[document.body?.innerText||'', ...state.texts().filter(item=>item.visible).map(item=>item.text),...state.canvasTexts()].filter(Boolean);
  state.startTargets=()=>allObjects().filter(({object})=>object.visible&&object.input?.enabled&&
    /play|start|jogar|iniciar|continuar|replay|next/i.test([object.texture?.key,object.texture?.__baltigoLabel,object.text].join(' ')))
    .map(({object,scene})=>({x:object.x,y:object.y,text:object.text||object.texture?.key,scene:scene.sys.settings.key}));
  state.interactive=()=>allObjects().filter(({object})=>object.visible&&object.input?.enabled).map(({object})=>({x:object.x,y:object.y,text:object.text||object.texture?.key||object.type}));

  // Observe actual score fields in running scenes. A progress report is never a
  // completed match. End messages require an actual result screen/state change.
  let lastProgress='';let lastFinish='';let lastResult='';
  let sentReady=false;
  function gameReady(){
    state.games.forEach(fitFlexCanvas);
    for(const game of state.games)for(const scene of game.scene?.getScenes(true)||[]){fitGamePresentation(scene);fitResultBackdrop(scene);fitTerminalConfirmation(scene);}
    if(sentReady)return;
    const ready=state.games.length
      ?state.games.some(game=>(game.scene?.scenes||[]).some(scene=>scene.sys?.isActive()&&!/boot|preload|loading/i.test(scene.sys.settings.key)&&scene.children?.list?.length>0&&!scene.load?.isLoading()))
      :document.readyState==='complete'&&Boolean(document.querySelector('canvas,button,[role="button"]'));
    if(ready){sentReady=true;if(state.status==='loading')state.status='ready';send('baltigo:ready');if(awaitingRoundInput&&gameInfo.slug==='sudoku')startRound();}
  }
  function report() {
    state.reportCount=(state.reportCount||0)+1;
    gameReady();
    let score=null;let outcome=null;let ended=false;
    for(const game of state.games) for(const scene of game.scene?.scenes||[]) {
      if(!scene.sys?.isActive())continue;
      for(const source of [scene,scene.state]) for(const field of ['score','_score','finalScore','coinsCollected','points','totalScore']) {
        if(source&&Number.isFinite(source[field])&&source[field]>=0) score=Math.max(score??0,source[field]);
      }
      const key=String(scene.sys.settings.key||'');
      if(/^(WinScene|GameOverScene|LoseScene|VictoryScene|ResultScene)$/i.test(key)) {
        ended=true;outcome=/Win|Victory/i.test(key)?'win':/Lose/i.test(key)?'lose':'finished';
      }
      if(scene.isGameOver===true||scene.gameOver===true||scene._gameOver===true||scene._finished===true||scene.state?.finished===true||scene.state==='gameover'||scene.state==='win'||scene.state==='lose') {
        ended=true;outcome=scene.isWin===true||scene.state==='win'?'win':scene.isWin===false||scene.state==='lose'?'lose':'finished';
      }
      if(/^(won|win|lost|lose|gameover|completed)$/.test(scene.gameState||'')){
        ended=true;outcome=/^(won|win|completed)$/.test(scene.gameState)?'win':'lose';
      }
    }
    const terminalText=allObjects().find(({object})=>effectiveVisible(object)&&typeof object.text==='string'&&/^(?:Fase concluída|Nível concluído|Você venceu|VOCÊ VENCEU|Fim de jogo|FIM DE JOGO|Você perdeu|VOCÊ PERDEU)[!.\s]*$/u.test(object.text.split('\n')[0].trim()));
    if(terminalText){ended=true;outcome=/concluíd|venceu|VENCEU/.test(terminalText.object.text)?'win':'lose';}
    // A few standalone games expose their score only through the HUD.
    if(score===null) {
      const hud=document.querySelector('#score,#scoreValue,#hud-score,[data-score]');
      if(hud&&/^\s*(?:Pontos|Pontuação|Score)?\s*:?\s*[0-9]+\s*$/i.test(hud.textContent)) {
        score=Number(hud.textContent.replace(/[^0-9]/g,''));
      }
    }
    const title=document.querySelector('#status-title,#result-title,#resultTitle,#overlay-title,#end-title,#end-message');
    if(title&&title.getClientRects().length&&getComputedStyle(title).visibility!=='hidden') {
      const text=title.innerText.trim();
      if(/^(Você venceu|VOCÊ VENCEU|Fim de jogo|FIM DE JOGO|Você perdeu|Empate|Fase concluída|FASE CONCLUÍDA)/.test(text)){
        ended=true;outcome=/perdeu|PERDEU|Fim|FIM/.test(text)?'lose':/venceu|VENCEU|concluída|CONCLUÍDA/.test(text)?'win':'finished';
      }
    }
    for(const [selector,result]of [['#win,#winOverlay,#winMessage,#centerMessage .win-title','win'],['#lose,#loseOverlay,#centerMessage .lose-title','lose']]){
      const overlay=document.querySelector(selector);
      if(overlay&&overlay.getClientRects().length&&getComputedStyle(overlay).visibility!=='hidden'){
        ended=true;outcome=result;
      }
    }
    const timer=document.querySelector('#timer');
    if(gameInfo.slug==='sudoku'&&timer&&/tempo acabou|tempo esgotado/i.test(timer.textContent)){ended=true;outcome='lose';}
    if(gameInfo.slug==='chess')for(const game of state.games)for(const scene of game.scene?.getScenes(true)||[]){
      if(scene.gameOver===true&&scene.pos&&typeof scene.pos.inCheck==='function'){
        ended=true;outcome=scene.pos.inCheck(scene.pos.side)?scene.pos.side!==scene.humanSide?'win':'lose':'draw';
      }
      if(scene.winOverlay?.visible&&/vitória de (brancas|pretas)/i.test(scene.winMsg?.text||'')){ended=true;outcome=/brancas/i.test(scene.winMsg.text)?'win':'lose';}
    }
    if(score!==null){state.score=score;const key=String(score);if(key!==lastProgress){lastProgress=key;send('baltigo:score',{score,event:'progress'});}}
    if(ended&&score!==null){const key=`${score}:${outcome}`;state.outcome=outcome;if(key!==lastFinish){lastFinish=key;send('baltigo:score',{score,event:'finish',outcome});}}
    if(ended){const key=`${score}:${outcome}`;state.status='finished';state.outcome=outcome;if(key!==lastResult){lastResult=key;send('baltigo:result',{score,outcome});}}
    if(!ended){lastFinish='';lastResult='';}
  }
  function localizeNode(node) {
    if(node.nodeType===Node.TEXT_NODE) {
      if(/^(SCRIPT|STYLE|NOSCRIPT|CODE|PRE)$/.test(node.parentElement?.tagName||'')) return;
      const value=translate(node.nodeValue);if(value!==node.nodeValue)node.nodeValue=value;
    } else if(node.nodeType===Node.ELEMENT_NODE) {
      if(/^(SCRIPT|STYLE|NOSCRIPT|CODE|PRE)$/.test(node.tagName))return;
      if(node.tagName==='CANVAS')for(const game of state.games)if(game.canvas===node)fitFlexCanvas(game);
      if(/^(next|nextBtn|nextButton|nextButtonWin)$/.test(node.id)&&/^(continuar|next)$/i.test(node.textContent.trim()))node.textContent='Nova partida';
      if(documentReplay&&node.tagName==='BUTTON'&&/^(continuar|next)$/i.test(node.textContent.trim()))node.textContent='Nova partida';
      for(const attribute of ['title','placeholder','aria-label','alt']) if(node.hasAttribute(attribute)){
        const value=node.getAttribute(attribute);const next=translate(value);if(value!==next)node.setAttribute(attribute,next);
      }
      for(const child of [...node.childNodes])localizeNode(child);
    }
  }
  function ready() {
    state.domReady=true;
    state.readyPhase='begin';
    document.documentElement.lang='pt-BR';
    if(gameInfo.orientation)send('baltigo:orientation',{orientation:gameInfo.orientation,logicalWidth:gameInfo.logical_width,logicalHeight:gameInfo.logical_height});
    if(gameInfo.name)document.title=gameInfo.name+' | Baltigo Games';
    state.readyPhase='orientation';
    localizeNode(document.body);
    state.readyPhase='localized';
    if(gameInfo.slug==='level-devil')addTunnelControls();
    document.addEventListener('click',event=>{
      if(gameInfo.slug==='sudoku'&&event.target.closest('#newGameBtn')){report();reloadRound();event.preventDefault();event.stopImmediatePropagation();return;}
      const button=event.target.closest('button,[role="button"],input[type="button"]');
      if(documentReplay&&button&&/^(nova partida|continuar|next)$/i.test(button.innerText.trim())){report();reloadRound();event.preventDefault();event.stopImmediatePropagation();return;}
      if(documentReplay&&button&&/^(jogar novamente|reiniciar|tentar novamente|repetir fase|replay|restart)$/i.test(button.innerText.trim())){report();reloadRound();event.preventDefault();event.stopImmediatePropagation();return;}
      if(button&&/^(continuar|nova partida|next)$/i.test(button.innerText.trim()))lastRoundConfirmation=originalNow();
      else if(button&&/^(jogar|jogar novamente|reiniciar|começar|tentar novamente|lançar dado|play|start|restart|replay)/i.test(button.innerText.trim())){
        startRound();
      }
    },true);
    document.addEventListener('pointerdown',event=>{
      if(gameInfo.slug==='sudoku'&&event.target.closest('#newGameBtn')){report();reloadRound();event.preventDefault();event.stopImmediatePropagation();return;}
      if(awaitingRoundInput&&event.target.closest('canvas,button,[role="button"]'))startRound();
      if(gameInfo.slug==='crossy-road'&&event.target.closest('#howToPlay'))startRound();
      if(gameInfo.slug==='archer'&&event.target.closest('#instructions'))startRound();
      const button=event.target.closest('button,[role="button"],input[type="button"]');
      if(documentReplay&&button&&/^(nova partida|continuar|next)$/i.test(button.innerText.trim())){report();reloadRound();event.preventDefault();event.stopImmediatePropagation();return;}
      if(documentReplay&&button&&/^(jogar novamente|reiniciar|tentar novamente|repetir fase|replay|restart)$/i.test(button.innerText.trim())){report();reloadRound();event.preventDefault();event.stopImmediatePropagation();return;}
      if(button&&/^(jogar|jogar novamente|reiniciar|começar|tentar novamente|lançar dado|nova partida|play|start|restart|replay)/i.test(button.innerText.trim()))startRound();
      if(button&&(/^(continuar|nova partida|next)$/i.test(button.innerText.trim())||/\bcompleteAndRestart\b/.test(String(button.onclick))))lastRoundConfirmation=originalNow();
    },true);
    new MutationObserver(changes=>{
      for(const change of changes){if(change.type==='characterData')localizeNode(change.target);else change.addedNodes.forEach(localizeNode);}
    }).observe(document.body,{childList:true,subtree:true,characterData:true});
    state.readyPhase='observing';
    state.reportTimer=setInterval(report,800);
    state.readyPhase='scheduled';
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',ready,{once:true});else ready();

  function addTunnelControls(){
    const pad=document.createElement('div');pad.id='baltigo-touch-controls';
    pad.setAttribute('aria-label','Controles do jogo');
    pad.style.cssText='position:fixed;z-index:2147483000;left:16px;right:16px;bottom:max(18px,env(safe-area-inset-bottom));display:flex;justify-content:space-between;pointer-events:none;';
    for(const [key,label,path]of [
      ['ArrowLeft','Mover para a esquerda','M15 5l-7 7 7 7'],
      ['ArrowRight','Mover para a direita','M9 5l7 7-7 7'],
    ]){
      const button=document.createElement('button');button.type='button';button.setAttribute('aria-label',label);
      button.innerHTML=`<svg width="28" height="28" viewBox="0 0 24 24" aria-hidden="true"><path d="${path}" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
      button.style.cssText='width:68px;height:62px;border:1px solid #80e9cf66;border-radius:18px;background:#0b172be6;color:#9ff7dc;box-shadow:0 8px 24px #0006;display:grid;place-items:center;pointer-events:auto;touch-action:none;user-select:none;';
      let held=false;
      const dispatch=type=>document.dispatchEvent(new KeyboardEvent(type,{key,code:key,bubbles:true,keyCode:key==='ArrowLeft'?37:39,which:key==='ArrowLeft'?37:39}));
      button.addEventListener('pointerdown',event=>{event.preventDefault();event.stopPropagation();held=true;button.setPointerCapture(event.pointerId);button.style.background='#173c43';dispatch('keydown');});
      const release=()=>{if(!held)return;held=false;button.style.background='#0b172be6';dispatch('keyup');};
      for(const event of ['pointerup','pointercancel','lostpointercapture'])button.addEventListener(event,release);
      window.addEventListener('blur',release);pad.append(button);
    }
    document.body.append(pad);
  }

  const originalRAF=window.requestAnimationFrame.bind(window);
  const originalCancelRAF=window.cancelAnimationFrame.bind(window);
  const originalTimeout=window.setTimeout.bind(window);
  const originalClearTimeout=window.clearTimeout.bind(window);
  const originalInterval=window.setInterval.bind(window);
  const originalNow=performance.now.bind(performance);
  const originalDateNow=Date.now.bind(Date);
  let pauseStarted=0;let pauseDuration=0;let pausedScenes=[];
  const currentPauseOffset=()=>pauseDuration+(state.paused?originalNow()-pauseStarted:0);
  // These clocks belong to this isolated game frame. Freeze its simulation
  // clock as well as RAF so Three.Clock and Date/performance based loops cannot
  // fast-forward after the portal tutorial/pause panel closes.
  try{Object.defineProperty(performance,'now',{configurable:true,value:()=>originalNow()-currentPauseOffset()});}catch{}
  Date.now=()=>originalDateNow()-currentPauseOffset();
  const pendingFrames=new Map();
  window.requestAnimationFrame=function(callback){
    let handle;
    const frame=time=>{
      if(!pendingFrames.has(handle))return;
      if(state.paused){pendingFrames.set(handle,originalRAF(frame));return;}
      pendingFrames.delete(handle);callback(time-pauseDuration);
    };
    handle=originalRAF(frame);pendingFrames.set(handle,handle);return handle;
  };
  window.cancelAnimationFrame=function(handle){const current=pendingFrames.get(handle);pendingFrames.delete(handle);originalCancelRAF(current??handle);};
  const pendingTimeouts=new Map();
  window.setTimeout=function(callback,delay=0,...args){
    if(typeof callback!=='function')return originalTimeout(callback,delay,...args);
    const wait=Math.max(0,Number(delay)||0);const due=performance.now()+wait;let handle;
    const tick=()=>{
      if(!pendingTimeouts.has(handle))return;
      const remaining=due-performance.now();
      if(state.paused||remaining>1){pendingTimeouts.set(handle,originalTimeout(tick,state.paused?80:remaining));return;}
      pendingTimeouts.delete(handle);callback(...args);
    };
    handle=originalTimeout(tick,wait);pendingTimeouts.set(handle,handle);return handle;
  };
  window.clearTimeout=function(handle){const current=pendingTimeouts.get(handle);pendingTimeouts.delete(handle);originalClearTimeout(current??handle);};
  window.setInterval=function(callback,delay,...args){
    if(typeof callback!=='function')return originalInterval(callback,delay,...args);
    return originalInterval(()=>{if(!state.paused)callback(...args);},delay);
  };
  function pause(paused) {
    if(state.paused===paused)return;
    if(paused){pauseStarted=originalNow();pausedScenes=[];}
    else pauseDuration+=originalNow()-pauseStarted;
    state.paused=paused;
    for(const game of state.games) {
      if(paused){for(const scene of game.scene?.scenes||[])if(scene.sys?.isActive()){pausedScenes.push(scene);scene.scene.pause();}game.sound?.pauseAll();}
      else game.sound?.resumeAll();
    }
    if(!paused){for(const scene of pausedScenes)if(scene.sys?.isPaused())scene.scene.resume();pausedScenes=[];}
    document.querySelectorAll('audio,video').forEach(media=>{
      if(paused&&!media.paused){media.dataset.baltigoResume='1';media.pause();}
      else if(!paused&&media.dataset.baltigoResume){delete media.dataset.baltigoResume;media.play().catch(()=>{});}
    });
  }
  window.addEventListener('message',event=>{
    if(event.source!==window.parent||event.origin!==location.origin)return;
    if(event.data?.type==='baltigo:pause')pause(Boolean(event.data.paused));
  });
  window.addEventListener('resize',()=>state.games.forEach(fitFlexCanvas));
  state.pause=pause;
  state.frameDiagnostics=()=>({pendingFrames:pendingFrames.size,pendingTimeouts:pendingTimeouts.size,realTime:originalNow(),activeTime:performance.now(),pauseDuration,visibility:document.visibilityState,focused:document.hasFocus(),engines:state.games.map(game=>({frame:game.loop.frame,running:game.loop.running,rafRunning:game.loop.raf?.isRunning,rafHandle:game.loop.raf?.timeOutID,focused:game.hasFocus,contextLost:game.renderer?.contextLost}))});
})();
