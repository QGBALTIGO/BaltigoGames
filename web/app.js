(() => {
  'use strict';
  const tg = window.Telegram?.WebApp;
  const $ = (id) => document.getElementById(id);
  const state = {games:[],categories:[],category:'all',query:'',view:'home',activeGame:null,favorites:new Set(),recent:[],tutorials:new Set(),rotations:{},rotationRequested:false,userId:'guest',displayName:'visitante',token:null,authenticated:false,sessionReady:null,playerStatus:'closed',run:null,runPending:null,playVersion:0,helpMode:null,closing:false,rankPeriod:'all',rankGame:'',rankVersion:0,scrollY:0,heroSlug:null,lastLauncher:null};
  const fullscreen = {pending:null,sequence:0,timer:null,browserOwned:false,preferBrowser:false,exitOnConfirmation:false,awaitingEnter:false};
  const CATEGORY_LABELS = {puzzle:'Quebra-cabeças',arcade:'Fliperama',shooter:'Tiro',racing:'Corrida',sports:'Esportes',platformer:'Plataforma',casual:'Casuais',board:'Tabuleiro','word-quiz':'Palavras e perguntas','3d':'Jogos em 3D'};
  const FEATURED = ['tetris','snake','2048','pacman','bubble-shooter','car-race','chess','crossy-road'];
  const popular = {status:'loading',entries:[],fetchedAt:0,pending:null,updatedAt:null,policy:''};
  const POPULAR_TTL = 60000;
  const NAME_FALLBACKS = {'space-fighter':'Combate espacial',snake:'Cobrinha',tetris:'Tetris','car-race':'Corrida de carros',chess:'Xadrez','bubble-shooter':'Estoura-bolhas','crossy-road':'Travessia','tic-tac-toe':'Jogo da velha','memory-cards':'Jogo da memória',flappy:'Voo sem fim',football:'Futebol',basketball:'Basquete',wordle:'Palavra do dia','endless-runner':'Corrida sem fim',sudoku:'Sudoku',pacman:'Pac-Man','2048':'2048'};
  const DEFAULT_CONTROLS = {racing:'No celular, toque nos controles do jogo ou deslize para mudar de direção. No computador, use as setas do teclado.',shooter:'Toque ou clique para mirar e disparar. Quando houver controles de movimento, use os botões na tela ou as setas.',puzzle:'Toque ou clique nas peças para fazer sua jogada. Alguns desafios também aceitam as setas do teclado.',arcade:'Use os botões exibidos no jogo ou toque na área da partida. No computador, experimente as setas e a barra de espaço.',board:'Toque ou clique na peça e depois na posição desejada. Aguarde sua vez antes de jogar.',platformer:'Use os controles da tela para andar e pular. No computador, use as setas e a barra de espaço.',casual:'Toque ou clique na área do jogo para interagir. Siga o objetivo e os controles da partida.',sports:'Use os controles da tela para direcionar a jogada. Toque ou clique para executar a ação indicada.','word-quiz':'Toque nas letras ou nas respostas da tela. Se houver um campo de resposta, use o teclado do seu aparelho.','3d':'Use os controles indicados na tela. No computador, as setas ou as teclas W, A, S e D costumam controlar o movimento.'};
  const GAME_CONTROLS = {tetris:'No celular, deslize para os lados para mover e use os botões inferiores para girar, acelerar e soltar a peça. No computador: setas laterais para mover, seta para cima para girar, seta para baixo para acelerar e espaço para soltar.','car-race':'No celular, deslize para a esquerda ou a direita para trocar de faixa. No computador, use as setas laterais ou as teclas A e D. O carro acelera automaticamente.'};
  const els = {app:$('app'),frame:$('gameFrame'),player:$('player'),loader:$('playerLoader'),pause:$('pausePanel'),playerError:$('playerError'),dialog:$('helpDialog'),helpContent:$('helpContent'),search:$('searchInput'),exploreSearch:$('exploreSearch'),homeGrid:$('homeGrid'),exploreGrid:$('exploreGrid'),favoritesGrid:$('favoritesGrid'),recentGrid:$('recentGrid'),featuredRail:$('featuredRail'),recentRail:$('recentRail'),categoryStrip:$('categoryStrip'),exploreCategories:$('exploreCategories'),toast:$('toast')};
  const icon = (name) => `<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const cleanName = (value) => String(value || '').replace(/[\p{Extended_Pictographic}\uFE0F\u200D]/gu,'').trim().slice(0,70) || 'Jogador';
  const gameName = (game) => game.name_pt || NAME_FALLBACKS[game.slug] || game.name || 'Jogo';
  const catLabel = (id) => CATEGORY_LABELS[id] || 'Outros jogos';
  const normalize = (value) => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('pt-BR');
  const number = (value) => new Intl.NumberFormat('pt-BR').format(Math.max(0,Number(value)||0));
  const coverUrl = (game) => {
    const cover=typeof game.cover==='string'&&game.cover.startsWith('/static/covers/')?game.cover:`/static/covers/${encodeURIComponent(game.slug)}.webp`;
    return game.slug==='planet-visitor'?`${cover}${cover.includes('?')?'&':'?'}v=20261025-arcade-5`:cover;
  };
  function coverPosition(game){
    const parts=typeof game.cover_position==='string'?game.cover_position.trim().split(/\s+/):[];
    if(parts.length!==2||parts.some(value=>!/^\d+(?:\.\d+)?%$/.test(value)))return '50% 50%';
    const values=parts.map(value=>Number.parseFloat(value));
    return values.every(value=>Number.isFinite(value)&&value>=0&&value<=100)?values.map(value=>value+'%').join(' '):'50% 50%';
  }
  function getStored(key,fallback){try{return JSON.parse(localStorage.getItem(key)) ?? fallback;}catch{return fallback;}}
  function putStored(key,value){try{localStorage.setItem(key,JSON.stringify(value));}catch{}}
  const storageKey = (kind) => `baltigogames:${state.userId}:${kind}`;
  function loadUserData(){
    // Keep the original keys so existing favorites and history survive the redesign.
    const favoriteData=getStored(storageKey('favorites'),[]),recentData=getStored(storageKey('recent'),[]),tutorialData=getStored(storageKey('tutorials'),[]);
    state.favorites=new Set(Array.isArray(favoriteData)?favoriteData.filter(s=>typeof s==='string'):[]);
    state.recent=Array.isArray(recentData)?recentData.filter(s=>typeof s==='string').slice(0,30):[];
    state.tutorials=new Set(Array.isArray(tutorialData)?tutorialData:[]);
    // Older versions presented rotation where players expected fullscreen.
    // Start the new, explicitly chosen rotation preference without changing user data.
    const rotations=getStored(storageKey('rotations-v2'),{});state.rotations=rotations&&typeof rotations==='object'&&!Array.isArray(rotations)?rotations:{};
    $('welcomeBanner').hidden=getStored('baltigogames:welcome-dismissed',false)===true;
  }
  function saveUserData(){putStored(storageKey('favorites'),[...state.favorites]);putStored(storageKey('recent'),state.recent);putStored(storageKey('tutorials'),[...state.tutorials]);putStored(storageKey('rotations-v2'),state.rotations);}
  function notify(message){clearTimeout(notify.timer);els.toast.textContent=message;els.toast.classList.add('toast--show');notify.timer=setTimeout(()=>els.toast.classList.remove('toast--show'),3500);}
  function haptic(style='light'){try{tg?.HapticFeedback?.impactOccurred(style);}catch{}}

  function confirmedFullscreen(){return Boolean(tg?.isFullscreen||document.fullscreenElement||document.webkitFullscreenElement);}
  function telegramFullscreenSupported(){
    if(typeof tg?.requestFullscreen!=='function'||typeof tg?.exitFullscreen!=='function')return false;
    try{return typeof tg.isVersionAtLeast!=='function'||tg.isVersionAtLeast('8.0');}catch{return false;}
  }
  function clearFullscreenRequest(){clearTimeout(fullscreen.timer);fullscreen.timer=null;fullscreen.pending=null;}
  function syncFullscreenButton(){
    const active=confirmedFullscreen(),button=$('playerFullscreen');if(!button)return;
    if(fullscreen.pending&&fullscreen.pending.enter===active){
      if(active)fullscreen.awaitingEnter=false;
      else if(!state.activeGame)fullscreen.exitOnConfirmation=false;
      clearFullscreenRequest();
    }
    button.setAttribute('aria-pressed',String(active));button.setAttribute('aria-busy',String(Boolean(fullscreen.pending)));
    button.disabled=Boolean(fullscreen.pending);
    button.setAttribute('aria-label',active?'Sair da tela cheia':'Entrar em tela cheia');button.title=active?'Sair da tela cheia':'Tela cheia';
    button.innerHTML=icon(active?'fullscreen-exit':'fullscreen');
    els.player.dataset.fullscreen=String(active);els.player.dataset.fullscreenPending=fullscreen.pending?(fullscreen.pending.enter?'enter':'exit'):'';
    document.body.classList.toggle('is-player-fullscreen',active&&Boolean(state.activeGame));
  }
  function fullscreenFailure(code,quiet=false){
    if(fullscreen.pending?.source==='browser'&&fullscreen.pending.enter&&!document.fullscreenElement&&!document.webkitFullscreenElement)fullscreen.browserOwned=false;
    if(code!=='TIMEOUT')fullscreen.awaitingEnter=false;
    clearFullscreenRequest();els.player.dataset.fullscreenError=code;
    const messages={UNSUPPORTED:'A tela cheia não está disponível neste Telegram. Toque novamente para tentar pelo navegador.',NOT_SUPPORTED:'Este aparelho não oferece tela cheia. Você pode continuar jogando.',NOT_ALLOWED:'O navegador não autorizou a tela cheia. Toque novamente para tentar.',TIMEOUT:'A tela cheia não foi confirmada. Toque novamente para tentar.',FAILED:'Não foi possível mudar a tela cheia. Toque novamente para tentar.'};
    const message=messages[code]||messages.FAILED;
    if(!quiet&&state.activeGame){$('playerFullscreenMessage').textContent=message;$('playerFullscreenStatus').hidden=false;notify(message);}
    updateViewport();
  }
  function fullscreenChanged(){
    const active=confirmedFullscreen();
    if(active){fullscreen.awaitingEnter=false;$('playerFullscreenStatus').hidden=true;delete els.player.dataset.fullscreenError;}
    if(!active&&!state.activeGame&&!fullscreen.pending?.enter&&!fullscreen.awaitingEnter)fullscreen.exitOnConfirmation=false;
    if(!document.fullscreenElement&&!document.webkitFullscreenElement)fullscreen.browserOwned=false;
    if(fullscreen.exitOnConfirmation&&!state.activeGame&&active){requestPlayerFullscreen(false,{quiet:true});return;}
    updateViewport();requestAnimationFrame(updateViewport);
  }
  function requestPlayerFullscreen(enter,{quiet=false,automatic=false}={}){
    if(fullscreen.pending||(!state.activeGame&&enter))return;
    if(confirmedFullscreen()===enter){syncFullscreenButton();return;}
    const native=tg?.isFullscreen===true||(!fullscreen.preferBrowser&&telegramFullscreenSupported());
    if(automatic&&!native){syncFullscreenButton();return;}
    const id=++fullscreen.sequence;fullscreen.pending={id,enter,source:native?'telegram':'browser',quiet};
    fullscreen.awaitingEnter=enter;
    $('playerFullscreenStatus').hidden=true;delete els.player.dataset.fullscreenError;
    fullscreen.timer=setTimeout(()=>{if(fullscreen.pending?.id===id)fullscreenFailure('TIMEOUT',quiet);},5000);
    syncFullscreenButton();
    try{
      let result;
      if(native){
        if(!telegramFullscreenSupported())throw new Error('NOT_SUPPORTED');
        result=enter?tg.requestFullscreen():tg.exitFullscreen();
      }else if(enter){
        const method=document.documentElement.requestFullscreen||document.documentElement.webkitRequestFullscreen;
        if(typeof method!=='function')throw new Error('NOT_SUPPORTED');
        fullscreen.browserOwned=true;
        result=method===document.documentElement.requestFullscreen?method.call(document.documentElement,{navigationUI:'hide'}):method.call(document.documentElement);
      }else{
        const method=document.exitFullscreen||document.webkitExitFullscreen;
        if(typeof method!=='function')throw new Error('NOT_SUPPORTED');
        result=method.call(document);
      }
      // The method returning is not confirmation. Read the real SDK/DOM state.
      syncFullscreenButton();updateViewport();
      if(result&&typeof result.then==='function')result.then(()=>fullscreenChanged()).catch(error=>{
        if(fullscreen.pending?.id!==id)return;
        fullscreenFailure(error?.name==='NotAllowedError'?'NOT_ALLOWED':'FAILED',quiet);
      });
    }catch(error){if(fullscreen.pending?.id===id)fullscreenFailure(error?.message==='NOT_SUPPORTED'?'NOT_SUPPORTED':error?.name==='NotAllowedError'?'NOT_ALLOWED':'FAILED',quiet);}
  }
  function togglePlayerFullscreen(){requestPlayerFullscreen(!confirmedFullscreen());}
  function exitPlayerFullscreen(){
    const entering=fullscreen.pending?.enter===true||fullscreen.awaitingEnter;
    fullscreen.sequence++;clearFullscreenRequest();fullscreen.exitOnConfirmation=entering||confirmedFullscreen();
    $('playerFullscreenStatus').hidden=true;delete els.player.dataset.fullscreenError;
    if(tg?.isFullscreen||((document.fullscreenElement||document.webkitFullscreenElement)&&fullscreen.browserOwned))requestPlayerFullscreen(false,{quiet:true});
    syncFullscreenButton();
  }
  function updateViewport(){
    const safe=tg?.safeAreaInset || {},content=tg?.contentSafeAreaInset || {};
    const inset=(edge)=>Math.max(0,Number(safe[edge])||0)+Math.max(0,Number(content[edge])||0);
    const full=Boolean(tg?.isFullscreen);
    // The device inset alone does not reserve Telegram's floating controls.
    // Reserve a separate native control row even when contentSafeArea reports zero.
    const deviceTop=Math.max(0,Number(safe.top)||0),contentTop=Math.max(0,Number(content.top)||0);
    const nativeTop=deviceTop+(contentTop>0?contentTop:56);
    const top=full?(window.innerHeight>=window.innerWidth&&deviceTop===0&&contentTop===0?96:nativeTop):inset('top');
    const root=document.documentElement.style;
    root.setProperty('--tg-safe-top',`${top}px`);root.setProperty('--tg-safe-bottom',`${inset('bottom')}px`);
    root.setProperty('--tg-safe-left',`${inset('left')}px`);root.setProperty('--tg-safe-right',`${inset('right')}px`);
    const height=confirmedFullscreen()?window.innerHeight:(Number(tg?.viewportHeight)||window.innerHeight);
    root.setProperty('--app-height',`${Math.round(height)}px`);
    syncFullscreenButton();
    updateGameViewport();
    if(state.helpMode==='orientation'&&window.innerWidth>window.innerHeight){state.helpMode=null;if(els.dialog.open)els.dialog.close();continueToGame();}
  }
  function initTelegram(){
    if(tg){
      try{tg.ready();tg.expand();tg.setHeaderColor('#080b24');tg.setBackgroundColor('#080b24');tg.setBottomBarColor?.('#080b24');}catch{}
      const user=tg.initDataUnsafe?.user;
      if(user){state.userId=String(user.id);state.displayName=cleanName(user.first_name || user.username);}
      try{tg.BackButton?.onClick(()=>{if(els.dialog.open)closeHelp();else closePlayer();});}catch{}
      ['viewportChanged','safeAreaChanged','contentSafeAreaChanged'].forEach(event=>{try{tg.onEvent(event,updateViewport);}catch{}});
      try{tg.onEvent('fullscreenChanged',fullscreenChanged);tg.onEvent('fullscreenFailed',event=>{
        const pending=fullscreen.pending;if(!pending)return;
        if(event?.error==='ALREADY_FULLSCREEN'&&tg.isFullscreen){fullscreenChanged();return;}
        if(event?.error==='UNSUPPORTED')fullscreen.preferBrowser=true;
        fullscreenFailure(event?.error==='UNSUPPORTED'?'UNSUPPORTED':'FAILED',pending.quiet);
      });}catch{}
    }
    $('profileName').textContent=state.displayName;$('profileInitial').textContent=state.displayName.charAt(0).toLocaleUpperCase('pt-BR');
    document.addEventListener('fullscreenchange',fullscreenChanged);document.addEventListener('webkitfullscreenchange',fullscreenChanged);
    document.addEventListener('fullscreenerror',()=>{setTimeout(()=>{if(fullscreen.pending?.source==='browser')fullscreenFailure('FAILED',fullscreen.pending.quiet);},0);});
    updateViewport();window.addEventListener('resize',updateViewport);window.visualViewport?.addEventListener('resize',updateViewport);
  }
  async function api(url,options={}){
    const headers={...options.headers};if(options.body)headers['Content-Type']='application/json';if(state.token)headers.Authorization=`Bearer ${state.token}`;
    const response=await fetch(url,{...options,headers,cache:'no-store'});
    if(!response.ok){const error=new Error(`request ${response.status}`);error.status=response.status;throw error;}
    return response.json();
  }
  async function establishSession(){
    if(!tg?.initData)return;
    try{const data=await api('/api/session',{method:'POST',body:JSON.stringify({init_data:tg.initData})});
      if(data.guest===false && typeof data.token==='string'){state.token=data.token;state.authenticated=true;if(data.user?.display_name){state.displayName=cleanName(data.user.display_name);$('profileName').textContent=state.displayName;$('profileInitial').textContent=state.displayName.charAt(0).toLocaleUpperCase('pt-BR');}}
    }catch{state.authenticated=false;}
  }
  async function loadCatalog(){
    $('catalogError').hidden=true;$('retryCatalog').disabled=true;
    if(!state.games.length){const skeleton=Array(10).fill('<div class="loading-skeleton" aria-hidden="true"></div>').join('');els.homeGrid.innerHTML=skeleton;}
    try{const data=await api('/api/catalog?v=20261025-arcade-6');
      state.games=(Array.isArray(data.games)?data.games:[]).filter(g=>/^[a-z0-9-]+$/.test(g.slug||'') && typeof g.path==='string' && g.path.startsWith('games/') && !g.path.includes('..'));
      state.categories=Array.isArray(data.categories)?data.categories:[];renderAll();configureHero();if(state.view==='home')loadPopularGames();
      $('heroCatalogCount').textContent=number(state.games.length);
      $('rankingGame').innerHTML='<option value="">Todos os jogos</option>'+[...state.games].sort((a,b)=>gameName(a).localeCompare(gameName(b),'pt-BR')).map(g=>`<option value="${escapeHtml(g.slug)}">${escapeHtml(gameName(g))}</option>`).join('');
      openFromStartParam();
    }catch{els.homeGrid.innerHTML='';$('catalogError').hidden=false;$('gameCount').textContent='Catálogo indisponível';if(!state.games.length)setPopularState('error');notify('O catálogo não carregou. Tente novamente.');}
    finally{$('retryCatalog').disabled=false;}
  }
  function configureHero(){
    state.heroGames=['tetris','car-race','fruit-merge'].map(slug=>state.games.find(g=>g.slug===slug)).filter(Boolean);if(!state.heroGames.length&&state.games[0])state.heroGames=[state.games[0]];
    $('heroPagination').innerHTML=state.heroGames.map((game,index)=>`<button type="button" class="hero-page" data-hero-index="${index}" aria-label="Mostrar destaque: ${escapeHtml(gameName(game))}" aria-pressed="${index===0}">${String(index+1).padStart(2,'0')}</button>`).join('');showHero(0);
    document.querySelectorAll('.arcade-cartridge').forEach(button=>{const game=state.games.find(game=>game.slug===button.dataset.game);const image=button.querySelector('img');if(game&&image)image.style.objectPosition=coverPosition(game);});
  }
  function showHero(index){const game=state.heroGames?.[index];if(!game)return;state.heroSlug=game.slug;state.heroIndex=index;$('heroImage').hidden=false;$('heroImage').src=coverUrl(game);$('heroImage').style.objectPosition=coverPosition(game);$('heroGameLabel').textContent=gameName(game);$('heroCartridgeName').textContent=gameName(game).toLocaleUpperCase('pt-BR');$('heroArtPlay').dataset.game=game.slug;$('heroArtPlay').setAttribute('aria-label',`Jogar ${gameName(game)}`);document.querySelectorAll('[data-hero-index]').forEach(button=>button.setAttribute('aria-pressed',String(Number(button.dataset.heroIndex)===index)));}
  function gameCard(game){
    const slug=escapeHtml(game.slug),name=escapeHtml(gameName(game)),fav=state.favorites.has(game.slug);
    return `<article class="game-card" data-game-card="${slug}"><div class="game-cover"><img src="${escapeHtml(coverUrl(game))}" style="object-position:${coverPosition(game)}" alt="Cena de ${name}" loading="lazy" decoding="async" width="480" height="360"/><button class="game-launch" type="button" data-game="${slug}" aria-label="Jogar ${name}"><span>${icon('play')}Jogar agora</span></button><button class="favorite-button" type="button" data-favorite="${slug}" aria-label="${fav?'Remover':'Salvar'} ${name} ${fav?'dos':'nos'} favoritos" aria-pressed="${fav}">${icon('heart')}</button></div><div class="game-info"><div><h3>${name}</h3><p>${escapeHtml(catLabel(game.category))}</p></div>${icon('chevron')}</div></article>`;
  }
  function setPopularState(status){
    popular.status=status;const section=$('popularSection');section.dataset.state=status;section.setAttribute('aria-busy',String(status==='loading'));
    $('popularLoading').hidden=status!=='loading';$('popularList').hidden=status!=='ready';$('popularEmpty').hidden=status!=='empty';$('popularError').hidden=status!=='error';
    $('popularPrev').disabled=true;$('popularNext').disabled=true;$('retryPopular').disabled=status==='loading';
    if(status!=='ready'){
      $('popularUpdated').textContent='Contagem geral';$('popularUpdated').removeAttribute('title');
      $('popularSummary').textContent={loading:'Consultando as partidas registradas da comunidade.',empty:'Seu próximo favorito pode estrear nesta lista.',error:'A biblioteca continua disponível para sua próxima partida.'}[status];
    }
    $('popularStatus').textContent=status==='error'?'Não foi possível carregar os jogos mais jogados.':status==='empty'?'Ainda não há jogos com partidas registradas.':'';
  }
  function updatePopularNavigation(){
    const list=$('popularList'),ready=popular.status==='ready'&&!list.hidden;
    $('popularPrev').disabled=!ready||list.scrollLeft<=2;
    $('popularNext').disabled=!ready||list.scrollLeft+list.clientWidth>=list.scrollWidth-2;
  }
  function movePopular(direction,oneCard=false){
    const list=$('popularList'),card=list.querySelector('[data-popular-game]');if(!card)return;
    const step=card.getBoundingClientRect().width+(Number.parseFloat(getComputedStyle(list).columnGap)||0);
    const distance=step*(oneCard?1:Math.max(1,Math.round(list.clientWidth/step)));
    list.scrollBy({left:direction*distance,behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth'});
  }
  function renderPopularGames(){
    const list=$('popularList');
    if(!popular.entries.length){list.replaceChildren();setPopularState('empty');return;}
    list.innerHTML=popular.entries.map(({game,plays},index)=>{
      const name=escapeHtml(gameName(game)),slug=escapeHtml(game.slug),count=number(plays),label=`${count} ${plays===1?'partida registrada':'partidas registradas'}`;
      return `<li class="popular-item" data-popular-game="${slug}"><button class="popular-game" type="button" data-game="${slug}" aria-label="Jogar ${name}, posição ${index+1} entre os mais jogados, ${label}"><span class="popular-cover"><img src="${escapeHtml(coverUrl(game))}" style="object-position:${coverPosition(game)}" alt="Cena de ${name}" loading="lazy" decoding="async" width="480" height="300"/><span class="popular-play" aria-hidden="true">${icon('play')}Jogar</span></span><span class="popular-info"><span class="popular-position"><span class="popular-rank" data-popular-rank aria-hidden="true">${String(index+1).padStart(2,'0')}</span><span class="popular-category">${escapeHtml(catLabel(game.category))}</span></span><strong class="popular-name">${name}</strong><span class="popular-plays" data-popular-plays>${label}</span></span></button></li>`;
    }).join('');
    setPopularState('ready');
    const count=popular.entries.length;
    $('popularSummary').textContent=count<10?`${number(count)} ${count===1?'jogo com partidas registradas':'jogos com partidas registradas'}. A lista cresce com a comunidade.`:'Os 10 jogos com mais partidas registradas. Escolha sua próxima partida.';
    $('popularStatus').textContent=`${number(count)} ${count===1?'jogo na lista dos mais jogados':'jogos na lista dos mais jogados'}.`;
    const updated=new Date(popular.updatedAt||'');
    if(Number.isFinite(updated.getTime())){$('popularUpdated').textContent=`Atualizado às ${updated.toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})}`;$('popularUpdated').title=updated.toLocaleString('pt-BR');}
    if(popular.policy)$('popularPolicy').textContent=popular.policy;
    list.scrollLeft=0;requestAnimationFrame(updatePopularNavigation);
  }
  function loadPopularGames(force=false){
    if(popular.pending)return popular.pending;
    if(!state.games.length)return Promise.resolve();
    if(!force&&Date.now()-popular.fetchedAt<POPULAR_TTL){if(popular.status==='ready')updatePopularNavigation();return Promise.resolve();}
    setPopularState('loading');const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),10000);
    const task=(async()=>{
      try{
        // Popularity is public: keep the HTTP cache and never attach a session token.
        const response=await fetch('/api/games/popular?limit=10',{credentials:'omit',cache:force?'reload':'default',signal:controller.signal});
        if(!response.ok)throw new Error('Popularidade indisponível');
        const data=await response.json();if(!Array.isArray(data.games)||data.period!=='all')throw new Error('Resposta inválida');
        const games=new Map(state.games.map(game=>[game.slug,game])),seen=new Set(),entries=[];
        for(const row of data.games){
          if(entries.length>=10)break;
          if(!row||!games.has(row.slug)||seen.has(row.slug)||!Number.isSafeInteger(row.plays)||row.plays<1)continue;
          seen.add(row.slug);entries.push({game:games.get(row.slug),plays:row.plays});
        }
        if(data.games.length&&!entries.length)throw new Error('Jogos indisponíveis');
        popular.entries=entries;popular.updatedAt=data.updated_at;popular.policy=typeof data.trust_policy==='string'?data.trust_policy.slice(0,1200):'';
        const responseDate=Date.parse(response.headers.get('Date')||''),headerAge=Number(response.headers.get('Age'))||0;
        const cacheAge=Math.max(0,headerAge*1000,Number.isFinite(responseDate)?Date.now()-responseDate:0);
        popular.fetchedAt=Date.now()-Math.min(POPULAR_TTL,cacheAge);renderPopularGames();
      }catch{popular.entries=[];popular.fetchedAt=Date.now();$('popularList').replaceChildren();setPopularState('error');}
      finally{clearTimeout(timeout);popular.pending=null;}
    })();popular.pending=task;return task;
  }
  function matchingGames(){const query=normalize(state.query.trim());return state.games.filter(game=>(state.category==='all'||game.category===state.category)&&(!query||normalize([gameName(game),game.name,game.slug,catLabel(game.category),game.description_pt,...(game.tags||[])].join(' ')).includes(query)));}
  function renderCategories(){
    const ids=[...new Set(state.games.map(g=>g.category))];const categories=[{id:'all',label:'Todos',count:state.games.length},...ids.map(id=>({id,label:catLabel(id),count:state.games.filter(g=>g.category===id).length}))];
    const html=categories.map(c=>`<button class="category-chip" type="button" data-category="${escapeHtml(c.id)}" aria-pressed="${state.category===c.id}">${escapeHtml(c.label)}<small>${c.count}</small></button>`).join('');
    [els.categoryStrip,els.exploreCategories].forEach(strip=>{const scroll=strip.scrollLeft;strip.innerHTML=html;strip.scrollLeft=scroll;});
  }
  function renderFavorites(){const games=state.games.filter(g=>state.favorites.has(g.slug));els.favoritesGrid.innerHTML=games.map(gameCard).join('');$('favoritesEmpty').hidden=games.length>0;}
  function renderRecent(){const bySlug=new Map(state.games.map(g=>[g.slug,g]));const games=state.recent.map(slug=>bySlug.get(slug)).filter(Boolean);els.recentGrid.innerHTML=games.map(gameCard).join('');els.recentRail.innerHTML=games.slice(0,8).map(gameCard).join('');$('recentSection').hidden=games.length===0;$('recentEmpty').hidden=games.length>0;}
  function renderAll(){
    renderCategories();const filtered=matchingGames(),html=filtered.map(gameCard).join('');els.homeGrid.innerHTML=html;els.exploreGrid.innerHTML=html;
    $('gameCount').textContent=`${number(filtered.length)} jogos`;$('exploreCount').textContent=`${number(filtered.length)} ${filtered.length===1?'jogo encontrado':'jogos encontrados'}`;
    $('emptyState').hidden=filtered.length>0;$('exploreEmpty').hidden=filtered.length>0;$('exploreReset').hidden=!state.query&&state.category==='all';
    els.featuredRail.innerHTML=FEATURED.map(slug=>state.games.find(g=>g.slug===slug)).filter(Boolean).map(gameCard).join('');renderFavorites();renderRecent();
  }
  function setQuery(value){state.query=value;els.search.value=value;els.exploreSearch.value=value;$('clearSearch').hidden=!value;renderAll();}
  function resetFilters(){state.category='all';setQuery('');}
  function toggleFavorite(slug){if(!state.games.some(g=>g.slug===slug))return;const active=!state.favorites.has(slug);if(active)state.favorites.add(slug);else state.favorites.delete(slug);saveUserData();
    document.querySelectorAll('[data-favorite]').forEach(button=>{if(button.dataset.favorite===slug){button.setAttribute('aria-pressed',String(active));const name=gameName(state.games.find(g=>g.slug===slug));button.setAttribute('aria-label',`${active?'Remover':'Salvar'} ${name} ${active?'dos':'nos'} favoritos`);}});
    renderFavorites();syncPlayerFavorite();haptic();notify(active?'Jogo salvo nos favoritos.':'Jogo removido dos favoritos.');
  }
  function syncPlayerFavorite(){const active=Boolean(state.activeGame&&state.favorites.has(state.activeGame.slug));$('playerFavorite').classList.toggle('playerFavorite--active',active);$('playerFavorite').setAttribute('aria-pressed',String(active));$('playerFavorite').setAttribute('aria-label',active?'Remover dos favoritos':'Salvar nos favoritos');}
  function setView(view){
    if(!['home','explore','ranking','favorites','recent'].includes(view))view='home';state.view=view;
    document.querySelectorAll('.view').forEach(section=>section.classList.toggle('view--active',section.dataset.view===view));
    document.querySelectorAll('[data-view-target]').forEach(button=>{const active=button.dataset.viewTarget===view;button.classList.toggle('nav-item--active',active);button.classList.toggle('nav-link--active',active);if(active)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');});
    window.scrollTo({top:0,behavior:'instant'});haptic();if(view==='ranking')loadLeaderboard();else if(view==='home')loadPopularGames();
  }

  function showDialog(mode){state.helpMode=mode;if(!els.dialog.open)els.dialog.showModal();els.dialog.scrollTop=0;}
  function showGeneralHelp(){
    $('helpEyebrow').textContent='SEU FLIPERAMA, DO SEU JEITO';
    els.helpContent.innerHTML=`<h2>Uma pausa.<br/>Infinitas possibilidades.</h2><p class="help-intro">Tudo pronto para jogar, sem instalar mais nada. Veja como aproveitar o Baltigo Games.</p><ol class="tutorial-steps"><li><span class="step-number">01</span><div><strong>Encontre seu próximo favorito</strong><p>Explore as categorias ou use a busca. Cada imagem mostra uma cena do próprio jogo.</p></div></li><li><span class="step-number">02</span><div><strong>Aprenda os controles antes de começar</strong><p>Cada jogo tem seu tutorial. Durante a partida, o botão de ajuda traz as instruções de volta e o botão de pausa dá um respiro.</p></div></li><li><span class="step-number">03</span><div><strong>Monte sua coleção e entre na disputa</strong><p>Salve seus favoritos no coração e volte pelo histórico. No Telegram, suas partidas podem render pontos de atividade na classificação geral.</p></div></li></ol><button class="primary-button dialog-primary" type="button" data-help-action="done">Entendi. Vamos jogar${icon('arrow')}</button>`;
    showDialog('general');
  }
  function tutorialDetails(game){
    const raw=game.instructions_pt||game.tutorial||game.description_pt||game.description;
    const instructions=Array.isArray(raw)?raw.filter(s=>typeof s==='string'):typeof raw==='string'?[raw]:[];
    const controls=Array.isArray(game.controls_pt)?game.controls_pt.join(' '):game.controls_pt||GAME_CONTROLS[game.slug]||DEFAULT_CONTROLS[game.category]||DEFAULT_CONTROLS.casual;
    return {instructions:instructions.length?instructions:['Siga o objetivo mostrado na partida e use os controles abaixo para começar.'],controls};
  }
  function showGameHelp(initial=false){
    const game=state.activeGame;if(!game)return;if(!initial)pauseGame(true);const details=tutorialDetails(game);
    $('helpEyebrow').textContent=`COMO JOGAR / ${catLabel(game.category).toLocaleUpperCase('pt-BR')}`;
    els.helpContent.innerHTML=`<div class="help-cover"><img src="${escapeHtml(coverUrl(game))}" style="object-position:${coverPosition(game)}" alt="Cena de ${escapeHtml(gameName(game))}"/></div><h2>${escapeHtml(gameName(game))}</h2><ol class="tutorial-steps">${details.instructions.map((text,index)=>`<li><span class="step-number">${String(index+1).padStart(2,'0')}</span><div><p>${escapeHtml(text)}</p></div></li>`).join('')}</ol><div class="controls-box"><strong>${icon('touch')}Seus controles</strong><p>${escapeHtml(details.controls)}</p></div>${initial?'<label class="tutorial-preference"><input id="skipGameTutorial" type="checkbox"/>Já aprendi. Não mostrar na próxima partida.</label>':''}<button class="primary-button dialog-primary" type="button" data-help-action="${initial?'start':'resume'}">${icon('play')}${initial?'Começar partida':'Voltar à partida'}</button>${initial?'<button class="text-button dialog-secondary" type="button" data-help-action="cancel">Escolher outro jogo</button>':''}`;
    showDialog(initial?'game-start':'game-help');
  }
  function closeHelp(){const mode=state.helpMode;state.helpMode=null;if(els.dialog.open)els.dialog.close();if(state.closing)return;if(mode==='game-start'||mode==='orientation')closePlayer();else if(mode==='game-help')resumeGame();}
  function showProfile(){
    $('helpEyebrow').textContent='SEU CANTO NO BALTIGO';
    els.helpContent.innerHTML=`<h2>Boa partida,<br/>${escapeHtml(state.displayName)}.</h2><div class="profile-status"><strong>${state.authenticated?'Perfil conectado ao Telegram':'Você está jogando como visitante'}</strong><p>${state.authenticated?'Suas partidas elegíveis participam da classificação por pontos de atividade.':'Para participar da classificação, abra o Baltigo Games pelo bot no Telegram. Seus favoritos e seu histórico continuam salvos neste aparelho.'}</p></div><div class="profile-stats"><div><strong>${number(state.favorites.size)}</strong><span>Jogos favoritos</span></div><div><strong>${number(state.recent.length)}</strong><span>Jogos no histórico</span></div></div><button class="primary-button dialog-primary" type="button" data-help-action="ranking">Ver classificação${icon('trophy')}</button><button class="text-button dialog-secondary" type="button" data-help-action="recent">Abrir meu histórico${icon('clock')}</button>`;showDialog('profile');
  }

  function sendGameMessage(type,extra={}){if(!state.activeGame)return;try{els.frame.contentWindow?.postMessage({type,...extra},location.origin);}catch{}}
  function landscapeGame(game){if(!game)return false;if(game.orientation)return game.orientation==='landscape';return Number(game.logical_width)>Number(game.logical_height)&&Number(game.logical_height)>0;}
  function handheldControls(){return ['android','ios'].includes(tg?.platform)||window.matchMedia('(pointer: coarse)').matches;}
  function updateGameViewport(){
    const stage=els.frame?.closest('.player-stage');if(!stage||els.player.hidden)return;
    const width=stage.clientWidth,height=stage.clientHeight;if(!width||!height)return;
    stage.style.setProperty('--stage-width',`${width}px`);stage.style.setProperty('--stage-height',`${height}px`);
    const rotated=state.rotationRequested&&height>width;stage.classList.toggle('is-rotated',rotated);
    $('playerRotate').hidden=!landscapeGame(state.activeGame)||width>=height;
    $('playerRotate').setAttribute('aria-pressed',String(rotated));$('playerRotate').setAttribute('aria-label',rotated?'Voltar a área do jogo para a vertical':'Girar a área do jogo para a horizontal');
  }
  function showOrientationHelp(){
    const game=state.activeGame;if(!game)return;
    $('helpEyebrow').textContent='ESSA MÁQUINA JOGA DE LADO';
    els.helpContent.innerHTML=`<div class="orientation-demo" aria-hidden="true"><span class="orientation-phone">${icon('gamepad')}</span><span class="orientation-arrow">${icon('rotate')}</span></div><h2>MAIS TELA.<br/>MAIS JOGO.</h2><p class="help-intro">${escapeHtml(gameName(game))} foi feito para a horizontal. Gire seu aparelho ou deixe a gente girar só a área da partida.</p><div class="orientation-benefit">${icon('check')}O jogo ganha espaço. Os controles do Baltigo continuam na posição normal.</div><button class="primary-button dialog-primary" type="button" data-help-action="rotate-start">${icon('rotate')}Girar a área e continuar</button><button class="text-button dialog-secondary" type="button" data-help-action="portrait-start">Continuar sem girar</button>`;
    showDialog('orientation');
  }
  function continueToGame(){if(!state.activeGame)return;updateGameViewport();if(state.tutorials.has(state.activeGame.slug))beginGame();else showGameHelp(true);}
  function selectOrientation(rotate){if(!state.activeGame)return;state.rotationRequested=rotate;state.rotations[state.activeGame.slug]=rotate;saveUserData();state.helpMode=null;if(els.dialog.open)els.dialog.close();updateGameViewport();continueToGame();}
  function toggleGameRotation(){if(!state.activeGame)return;state.rotationRequested=!state.rotationRequested;state.rotations[state.activeGame.slug]=state.rotationRequested;saveUserData();updateGameViewport();haptic();notify(state.rotationRequested?'Área do jogo na horizontal.':'Área do jogo na vertical.');}
  function openGame(slug){
    const game=state.games.find(g=>g.slug===slug);if(!game)return;if(state.activeGame)closePlayer();
    state.lastLauncher=document.activeElement;state.scrollY=window.scrollY;state.activeGame=game;state.playerStatus='tutorial';state.rotationRequested=handheldControls()&&state.rotations[slug]===true;state.playVersion++;
    $('playerTitle').textContent=gameName(game);$('playerCategory').textContent=catLabel(game.category).toLocaleUpperCase('pt-BR');els.frame.title=`Jogar ${gameName(game)}`;
    els.player.hidden=false;els.loader.hidden=false;els.pause.hidden=true;els.playerError.hidden=true;document.body.style.overflow='hidden';document.body.classList.add('is-playing');els.app.inert=true;document.querySelector('.bottom-nav').inert=true;syncPlayerFavorite();
    fullscreen.exitOnConfirmation=false;
    try{tg?.BackButton?.show();tg?.disableVerticalSwipes?.();}catch{}
    requestPlayerFullscreen(true,{automatic:true,quiet:true});updateViewport();
    history.pushState({player:slug},'',`#play=${encodeURIComponent(slug)}`);haptic('medium');
    updateGameViewport();
    if(landscapeGame(game)&&window.innerHeight>window.innerWidth&&handheldControls()&&!Object.prototype.hasOwnProperty.call(state.rotations,slug))showOrientationHelp();else continueToGame();
  }
  function beginGame(){
    const game=state.activeGame;if(!game)return;
    if($('skipGameTutorial')?.checked){state.tutorials.add(game.slug);saveUserData();}
    state.helpMode=null;if(els.dialog.open)els.dialog.close();state.playerStatus='loading';els.loader.hidden=false;els.pause.hidden=true;els.playerError.hidden=true;
    state.recent=[game.slug,...state.recent.filter(s=>s!==game.slug)].slice(0,30);saveUserData();renderRecent();
    const version=state.playVersion;const gameVersion=['cosmic-cleaner','spaceman'].includes(game.slug)?'20261025-8':'20261025-7';clearTimeout(beginGame.timer);els.frame.src=`/play-v3/${game.path}?v=${gameVersion}`;
    beginGame.timer=setTimeout(()=>{if(state.playVersion===version&&state.playerStatus==='loading'){els.loader.hidden=true;els.playerError.hidden=false;state.playerStatus='error';}},30000);
  }
  function markGameReady(){if(!state.activeGame||!['loading','paused'].includes(state.playerStatus))return;clearTimeout(beginGame.timer);els.loader.hidden=true;if(state.playerStatus==='loading'){state.playerStatus='playing';beginRankedRun();if(state.helpMode==='game-help'||document.hidden)pauseGame(state.helpMode==='game-help');}else sendGameMessage('baltigo:pause',{paused:true});}
  function pauseGame(forHelp=false){
    if(!state.activeGame||!['playing','paused'].includes(state.playerStatus))return;state.playerStatus='paused';sendGameMessage('baltigo:pause',{paused:true});els.pause.hidden=forHelp;heartbeat(false);haptic();
  }
  function resumeGame(){
    if(!state.activeGame||state.playerStatus!=='paused')return;state.helpMode=null;if(els.dialog.open)els.dialog.close();els.pause.hidden=true;state.playerStatus='playing';sendGameMessage('baltigo:pause',{paused:false});heartbeat(true);els.frame.focus();
  }
  function closePlayer(){
    if(!state.activeGame)return;state.closing=true;state.playVersion++;clearTimeout(beginGame.timer);finishRun('ended');state.activeGame=null;state.playerStatus='closed';state.helpMode=null;if(els.dialog.open)els.dialog.close();els.player.hidden=true;els.frame.src='about:blank';els.loader.hidden=false;els.pause.hidden=true;document.body.style.overflow='';document.body.classList.remove('is-playing');els.app.inert=false;document.querySelector('.bottom-nav').inert=false;
    try{tg?.BackButton?.hide();tg?.enableVerticalSwipes?.();}catch{}exitPlayerFullscreen();
    if(location.hash.startsWith('#play='))history.replaceState({},'',location.pathname+location.search);
    window.scrollTo({top:state.scrollY,behavior:'instant'});state.lastLauncher?.focus?.({preventScroll:true});state.closing=false;updateViewport();
  }
  async function restartGame(){if(!state.activeGame)return;const version=state.playVersion;await finishRun('ended');if(!state.activeGame||state.playVersion!==version)return;state.playVersion++;beginGame();haptic();}
  async function beginRankedRun(){
    const game=state.activeGame,version=state.playVersion;if(!game||state.run||state.runPending)return;
    const pending=(async()=>{await state.sessionReady;if(!state.authenticated||state.playVersion!==version||!state.activeGame)return;
      try{const data=await api('/api/runs',{method:'POST',body:JSON.stringify({game_slug:game.slug})});
        if(state.playVersion!==version||!state.activeGame){try{await api(`/api/runs/${encodeURIComponent(data.run_id)}/finish`,{method:'POST',body:JSON.stringify({outcome:'abandoned'})});}catch{}return;}
        state.run={id:data.run_id,slug:game.slug,started:Date.now(),score:null,finishing:false};heartbeat(state.playerStatus==='playing'&&!document.hidden);
      }catch(error){if(error.status===401){state.authenticated=false;state.token=null;}}
    })();state.runPending=pending;await pending;if(state.runPending===pending)state.runPending=null;if(state.activeGame&&state.playerStatus==='playing'&&!state.run&&state.playVersion!==version)beginRankedRun();
  }
  async function heartbeat(active){const run=state.run;if(!run||run.finishing)return;try{await api(`/api/runs/${encodeURIComponent(run.id)}/heartbeat`,{method:'POST',body:JSON.stringify({active:Boolean(active)})});}catch{}}
  async function finishRun(outcome='ended',score){
    const run=state.run;if(!run||run.finishing)return;run.finishing=true;state.run=null;
    const body={outcome,duration_ms:Math.max(0,Date.now()-run.started)};const value=Number.isFinite(score)?score:run.score;if(Number.isFinite(value)&&value>=0&&value<=1e9)body.score=value;
    try{const result=await api(`/api/runs/${encodeURIComponent(run.id)}/finish`,{method:'POST',body:JSON.stringify(body),keepalive:true});if(result.accepted&&result.points>0&&!result.duplicate)notify(`Partida registrada: ${number(result.points)} ${result.points===1?'ponto':'pontos'} de atividade.`);if(state.view==='ranking')loadLeaderboard();}catch{}
  }
  async function loadLeaderboard(){
    const version=++state.rankVersion;const status=$('rankingStatus');status.hidden=false;status.textContent='Carregando classificação…';$('leaderboard').hidden=true;$('rankingMe').hidden=true;
    try{await state.sessionReady;const params=new URLSearchParams({scope:'global',period:state.rankPeriod});if(state.rankGame)params.set('game',state.rankGame);const data=await api(`/api/leaderboard?${params}`);if(version!==state.rankVersion)return;
      const entries=Array.isArray(data.entries)?data.entries:[];
      if(data.trust_policy)$('rankingPolicy').textContent=data.trust_policy;
      if(!entries.length){status.innerHTML='<strong>A próxima história começa com você.</strong><p>Ainda não há partidas elegíveis neste período. Jogue pelo Telegram para começar a somar pontos de atividade.</p><button class="primary-button" type="button" data-go="explore">Escolher um jogo'+icon('arrow')+'</button>';}
      else{status.hidden=true;$('leaderboard').hidden=false;$('rankingEntries').innerHTML=entries.map(entry=>`<li class="ranking-row${entry.is_me?' ranking-row--me':''}"><div class="ranking-player"><span class="ranking-position">${number(entry.rank)}</span><span class="ranking-avatar" aria-hidden="true">${escapeHtml(cleanName(entry.display_name).charAt(0).toLocaleUpperCase('pt-BR'))}</span><span class="ranking-name">${escapeHtml(cleanName(entry.display_name))}${entry.is_me?'<small>VOCÊ</small>':''}</span></div><span class="ranking-played">${number(entry.games_played)}</span><strong class="ranking-points">${number(entry.points)}</strong></li>`).join('');}
      if(data.me){$('rankingMe').hidden=false;$('rankingMe').innerHTML=`<div><strong>${data.me.rank?`Sua posição: ${number(data.me.rank)}º lugar`:'Sua primeira posição começa com uma partida'}</strong><p>${number(data.me.games_played)} ${data.me.games_played===1?'partida registrada':'partidas registradas'} neste período</p></div><span class="ranking-me-score">${number(data.me.points)}<small>pontos de atividade</small></span>`;}
    }catch{if(version!==state.rankVersion)return;status.innerHTML='<strong>A classificação está indisponível.</strong><p>Não foi possível atualizar os resultados. Tente novamente em instantes.</p><button class="secondary-button" type="button" data-retry-ranking>Tentar novamente</button>';}
  }
  function onGameMessage(event){
    if(event.origin!==location.origin||event.source!==els.frame.contentWindow||!state.activeGame)return;let data=event.data;if(typeof data==='string'){try{data=JSON.parse(data);}catch{return;}}
    if(data?.type==='orientation'){if(!state.activeGame.orientation&&['landscape','portrait'].includes(data.value)){state.activeGame.orientation=data.value;updateGameViewport();}return;}
    if(!data||typeof data!=='object'||data.slug!==state.activeGame.slug)return;
    if(data.type==='baltigo:orientation'){if(!state.activeGame.orientation&&['landscape','portrait'].includes(data.orientation))state.activeGame.orientation=data.orientation;updateGameViewport();return;}
    if(data.type==='baltigo:fullscreen'){requestPlayerFullscreen(true,{automatic:true,quiet:true});return;}
    if(data.type==='baltigo:ready'){markGameReady();return;}
    if(data.type==='baltigo:start'){if(state.playerStatus==='playing'&&!state.run)beginRankedRun();return;}
    if(data.type==='baltigo:result'){finishRun(['win','completed'].includes(data.outcome)?'completed':'ended',Number.isFinite(data.score)?data.score:undefined);return;}
    if(data.type!=='baltigo:score'||!Number.isFinite(data.score)||data.score<0||data.score>1e9)return;
    if(state.run)state.run.score=data.score;
    if(data.event==='finish')finishRun(['win','completed'].includes(data.outcome)?'completed':'ended',data.score);
  }
  async function shareCatalog(){await shareLink('Baltigo Games','Descubra seu próximo jogo favorito no Baltigo Games.',location.origin);}
  async function shareLink(title,text,url){try{if(navigator.share){await navigator.share({title,text,url});return;}if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(url);notify('Link copiado. Compartilhe com quem vai jogar com você.');return;}if(tg?.switchInlineQuery){tg.switchInlineQuery('', ['users','groups']);return;}notify('Compartilhe o endereço desta página.');}catch(error){if(error.name!=='AbortError')notify('Não foi possível compartilhar agora.');}}
  function openFromStartParam(){if(openFromStartParam.done)return;openFromStartParam.done=true;const params=new URLSearchParams(location.search);const raw=tg?.initDataUnsafe?.start_param||params.get('tgWebAppStartParam')||params.get('startapp')||location.hash.match(/^#play=([a-z0-9-]+)/)?.[1];if(raw&&state.games.some(g=>g.slug===raw))openGame(raw);}

  function bindUI(){
    document.addEventListener('click',event=>{
      const favorite=event.target.closest('[data-favorite]');if(favorite){toggleFavorite(favorite.dataset.favorite);return;}
      const launch=event.target.closest('[data-game]');if(launch){openGame(launch.dataset.game);return;}
      const category=event.target.closest('[data-category]');if(category){state.category=category.dataset.category;renderAll();haptic();return;}
      const hero=event.target.closest('[data-hero-index]');if(hero){showHero(Number(hero.dataset.heroIndex));return;}
      const navigation=event.target.closest('[data-view-target],[data-go]');if(navigation){event.preventDefault();setView(navigation.dataset.viewTarget||navigation.dataset.go);return;}
      const period=event.target.closest('[data-period]');if(period){state.rankPeriod=period.dataset.period;document.querySelectorAll('[data-period]').forEach(button=>button.setAttribute('aria-pressed',String(button===period)));loadLeaderboard();return;}
      if(event.target.closest('[data-retry-ranking]')){loadLeaderboard();return;}
      const action=event.target.closest('[data-help-action]');if(action){
        if(action.dataset.helpAction==='rotate-start')selectOrientation(true);else if(action.dataset.helpAction==='portrait-start')selectOrientation(false);else if(action.dataset.helpAction==='start')beginGame();else if(action.dataset.helpAction==='resume'){state.helpMode=null;resumeGame();}else if(action.dataset.helpAction==='cancel')closePlayer();else if(action.dataset.helpAction==='ranking'||action.dataset.helpAction==='recent'){const view=action.dataset.helpAction;closeHelp();setView(view);}else closeHelp();
      }
    });
    document.addEventListener('error',event=>{const img=event.target;if(!(img instanceof HTMLImageElement))return;if(img.closest('.game-cover')){const parent=img.parentElement;img.remove();parent.classList.add('game-cover--unavailable');const span=document.createElement('span');span.className='cover-fallback';span.textContent=parent.querySelector('[data-game]')?.getAttribute('aria-label')?.replace(/^Jogar /,'')||'Baltigo Games';parent.prepend(span);}else img.hidden=true;},true);
    els.search.addEventListener('input',()=>setQuery(els.search.value));els.exploreSearch.addEventListener('input',()=>setQuery(els.exploreSearch.value));
    $('clearSearch').onclick=()=>setQuery('');$('resetFilters').onclick=resetFilters;$('exploreReset').onclick=resetFilters;$('retryCatalog').onclick=loadCatalog;
    $('retryPopular').onclick=()=>{if(!state.games.length)loadCatalog();else loadPopularGames(true);};
    $('popularPrev').onclick=()=>movePopular(-1);$('popularNext').onclick=()=>movePopular(1);
    $('popularList').addEventListener('scroll',updatePopularNavigation,{passive:true});
    $('popularList').addEventListener('keydown',event=>{
      if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
      const buttons=[...$('popularList').querySelectorAll('[data-game]')];if(!buttons.length)return;event.preventDefault();
      const focused=buttons.indexOf(event.target.closest('[data-game]'));
      if(focused<0&&['ArrowLeft','ArrowRight'].includes(event.key)){movePopular(event.key==='ArrowRight'?1:-1,true);return;}
      const index=event.key==='Home'?0:event.key==='End'?buttons.length-1:Math.max(0,Math.min(buttons.length-1,focused+(event.key==='ArrowRight'?1:-1)));
      buttons[index].focus({preventScroll:true});buttons[index].scrollIntoView({block:'nearest',inline:'nearest',behavior:'instant'});
    });
    if(window.ResizeObserver)new ResizeObserver(updatePopularNavigation).observe($('popularList'));
    $('heroPlayButton').onclick=()=>{if(state.heroSlug)openGame(state.heroSlug);};$('randomButton').onclick=()=>{const games=matchingGames();if(games.length)openGame(games[Math.floor(Math.random()*games.length)].slug);else notify('Escolha outra categoria para descobrir um jogo.');};
    $('helpButton').onclick=showGeneralHelp;$('welcomeHelp').onclick=showGeneralHelp;$('profileButton').onclick=showProfile;$('dismissWelcome').onclick=()=>{$('welcomeBanner').hidden=true;putStored('baltigogames:welcome-dismissed',true);};
    const hero=$('heroSection'),stage=hero.querySelector('.arcade-stage');
    hero.addEventListener('pointermove',event=>{if(!matchMedia('(hover:hover) and (prefers-reduced-motion:no-preference)').matches)return;const rect=hero.getBoundingClientRect();stage.style.setProperty('--hero-x',`${((event.clientX-rect.left)/rect.width-.5)*9}px`);stage.style.setProperty('--hero-y',`${((event.clientY-rect.top)/rect.height-.5)*6}px`);},{passive:true});
    hero.addEventListener('pointerleave',()=>{stage.style.setProperty('--hero-x','0px');stage.style.setProperty('--hero-y','0px');});
    $('closeHelp').onclick=closeHelp;els.dialog.addEventListener('cancel',event=>{event.preventDefault();closeHelp();});els.dialog.addEventListener('click',event=>{if(event.target===els.dialog){const box=els.dialog.getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)closeHelp();}});
    $('playerBack').onclick=closePlayer;$('pauseExit').onclick=closePlayer;$('playerErrorBack').onclick=closePlayer;$('playerFavorite').onclick=()=>{if(state.activeGame)toggleFavorite(state.activeGame.slug);};$('playerRotate').onclick=toggleGameRotation;$('playerFullscreen').onclick=togglePlayerFullscreen;$('playerFullscreenRetry').onclick=togglePlayerFullscreen;$('playerHelp').onclick=()=>showGameHelp(false);$('playerPause').onclick=()=>pauseGame(false);$('resumeGame').onclick=resumeGame;$('playerReload').onclick=restartGame;$('playerRetry').onclick=restartGame;
    $('shareCatalogButton').onclick=shareCatalog;$('rankingGame').onchange=()=>{state.rankGame=$('rankingGame').value;loadLeaderboard();};
    els.frame.addEventListener('load',()=>{if(!state.activeGame||els.frame.getAttribute('src')==='about:blank')return;try{const doc=els.frame.contentDocument;if(doc&&(/^(Not Found|Internal Server Error)$/i.test(doc.title)||doc.body?.textContent?.trim().startsWith('{"detail":'))){clearTimeout(beginGame.timer);els.loader.hidden=true;els.playerError.hidden=false;state.playerStatus='error';return;}}catch{}markGameReady();});
    window.addEventListener('message',onGameMessage);window.addEventListener('popstate',()=>{if(state.activeGame)closePlayer();});
    if(window.ResizeObserver)new ResizeObserver(updateGameViewport).observe(els.frame.closest('.player-stage'));
    window.addEventListener('keydown',event=>{if(event.key==='Escape'&&state.activeGame&&!els.dialog.open){event.preventDefault();if(state.playerStatus==='paused')resumeGame();else pauseGame();}});
    window.addEventListener('online',()=>{$('offlineBanner').hidden=true;});window.addEventListener('offline',()=>{$('offlineBanner').hidden=false;if(state.playerStatus==='playing')pauseGame();});$('offlineBanner').hidden=navigator.onLine;
    document.addEventListener('visibilitychange',()=>{if(document.hidden){if(state.playerStatus==='playing')pauseGame();else heartbeat(false);}});
    window.addEventListener('pagehide',()=>{heartbeat(false);finishRun('ended');});
    window.addEventListener('blur',()=>{setTimeout(()=>{if(state.playerStatus==='playing'&&!document.hasFocus())pauseGame();},100);});
    setInterval(()=>{if(state.playerStatus==='playing'&&!document.hidden&&document.hasFocus())heartbeat(true);},10000);
  }
  function init(){initTelegram();loadUserData();bindUI();state.sessionReady=establishSession();loadCatalog();}
  init();
})();
