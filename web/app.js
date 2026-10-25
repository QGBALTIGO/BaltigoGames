(() => {
  const tg = window.Telegram?.WebApp;
  const state = {
    games: [], categories: [], category: 'all', query: '', currentView: 'home', activeGame: null,
    favorites: new Set(), recent: [], userId: 'guest'
  };

  const CATEGORY_LABELS = {
    puzzle:'Puzzle', arcade:'Arcade', shooter:'Tiro', racing:'Corrida', sports:'Esportes',
    platformer:'Plataforma', casual:'Casual', board:'Tabuleiro', 'word-quiz':'Palavras & Quiz', '3d':'3D'
  };
  const CATEGORY_EMOJI = {puzzle:'🧩',arcade:'🕹️',shooter:'🎯',racing:'🏎️',sports:'⚽',platformer:'🏃',casual:'🎈',board:'♟️','word-quiz':'📝','3d':'🌐'};
  const GAME_EMOJI = {
    '2048':'🔢',tetris:'🟦',snake:'🐍','curve-snake':'🐍',chess:'♟️',ludo:'🎲','tic-tac-toe':'⭕',sudoku:'🔢',pacman:'👻',flappy:'🐤',mario:'🍄','doodle-jump':'⬆️','bubble-shooter':'🫧','candy-crush':'🍬','fruit-merge':'🍇',wordle:'🔤',football:'⚽',basketball:'🏀',bowling:'🎳',archer:'🏹','bird-shooter':'🐦','alien-battle':'👾','space-fighter':'🚀','car-race':'🏎️','road-fighter':'🚗','endless-runner':'🏃','crossy-road':'🐔','stack-tower':'🏗️','planet-war':'🪐','cut-rope':'✂️','memory':'🧠','memory-cards':'🧠','rock-paper-scissors':'✊','carrom':'🪙','penalty':'🥅','breakoid':'🧱','cooking':'👨‍🍳'
  };
  const PALETTES = [
    ['#6f3cff','#2b185c'],['#e04b9a','#5f193f'],['#ff8a3d','#6d2c16'],['#23a69a','#114a49'],
    ['#4169e1','#18295e'],['#b955db','#4a1b5d'],['#6d8f3e','#2c3f20'],['#d65362','#5b1f2c']
  ];
  const FEATURED = ['snake','2048','tetris','pacman','flappy','car-race','chess','crossy-road'];

  const $ = (id) => document.getElementById(id);
  const els = {
    profileName:$('profileName'),profileInitial:$('profileInitial'),search:$('searchInput'),clearSearch:$('clearSearch'),
    categoryStrip:$('categoryStrip'),homeGrid:$('homeGrid'),exploreGrid:$('exploreGrid'),favoritesGrid:$('favoritesGrid'),recentGrid:$('recentGrid'),
    featuredRail:$('featuredRail'),recentRail:$('recentRail'),recentSection:$('recentSection'),gameCount:$('gameCount'),emptyState:$('emptyState'),
    favoritesEmpty:$('favoritesEmpty'),recentEmpty:$('recentEmpty'),player:$('player'),frame:$('gameFrame'),loader:$('playerLoader'),
    playerTitle:$('playerTitle'),playerCategory:$('playerCategory'),playerFavorite:$('playerFavorite'),toast:$('toast'),offline:$('offlineBanner')
  };

  function storageKey(name){ return `baltigogames:${state.userId}:${name}`; }
  function safeParse(value, fallback){ try { return JSON.parse(value) ?? fallback; } catch { return fallback; } }
  function save(){ localStorage.setItem(storageKey('favorites'), JSON.stringify([...state.favorites])); localStorage.setItem(storageKey('recent'), JSON.stringify(state.recent)); }
  function loadUserData(){ state.favorites = new Set(safeParse(localStorage.getItem(storageKey('favorites')), [])); state.recent = safeParse(localStorage.getItem(storageKey('recent')), []).slice(0,30); }

  function initTelegram(){
    if (!tg) return;
    tg.ready(); tg.expand();
    try { tg.setHeaderColor('#09070f'); tg.setBackgroundColor('#09070f'); tg.setBottomBarColor?.('#09070f'); } catch {}
    const user = tg.initDataUnsafe?.user;
    if (user) {
      state.userId = String(user.id);
      const name = user.first_name || user.username || 'jogador';
      els.profileName.textContent = name;
      els.profileInitial.textContent = name.trim().charAt(0).toUpperCase() || 'B';
    }
    tg.BackButton?.onClick(closePlayer);
  }

  function haptic(kind='light'){ try { tg?.HapticFeedback?.impactOccurred(kind); } catch {} }
  function notify(message){ clearTimeout(notify.t); els.toast.textContent=message; els.toast.classList.add('toast--show'); notify.t=setTimeout(()=>els.toast.classList.remove('toast--show'),1800); }

  async function loadCatalog(){
    const res = await fetch('/api/catalog', {cache:'no-store'});
    if (!res.ok) throw new Error(`catalog ${res.status}`);
    const data = await res.json();
    state.games = Array.isArray(data.games) ? data.games : [];
    state.categories = Array.isArray(data.categories) ? data.categories : [];
    renderAll();
    openFromStartParam();
  }

  function hashCode(input){ let h=0; for(let i=0;i<input.length;i++) h=((h<<5)-h)+input.charCodeAt(i)|0; return Math.abs(h); }
  function palette(slug){ return PALETTES[hashCode(slug)%PALETTES.length]; }
  function emoji(game){ return GAME_EMOJI[game.slug] || CATEGORY_EMOJI[game.category] || '🎮'; }
  function catLabel(id){ return CATEGORY_LABELS[id] || id; }
  function escapeHtml(v){ return String(v ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

  function gameCard(game){
    const [g1,g2]=palette(game.slug); const fav=state.favorites.has(game.slug);
    return `<article class="game-card" data-game="${escapeHtml(game.slug)}" style="--g1:${g1};--g2:${g2}">
      <div class="game-cover">
        <button class="favorite-button" type="button" data-favorite="${escapeHtml(game.slug)}" data-active="${fav}" aria-label="Favoritar ${escapeHtml(game.name)}">${fav?'♥':'♡'}</button>
        <span class="game-emoji" aria-hidden="true">${emoji(game)}</span><span class="play-badge" aria-hidden="true">▶</span>
      </div>
      <div class="game-info"><h3>${escapeHtml(game.name)}</h3><p>${CATEGORY_EMOJI[game.category]||'🎮'} ${escapeHtml(catLabel(game.category))}</p><div class="meta-row"><span class="tech-pill">${escapeHtml((game.tech||'html').toUpperCase())}</span><span class="mini-dot"></span></div></div>
    </article>`;
  }

  function matchingGames(){
    const q=state.query.toLowerCase().trim();
    return state.games.filter(g=>{
      if(state.category!=='all' && g.category!==state.category) return false;
      if(!q) return true;
      const hay=[g.name,g.slug,g.category,catLabel(g.category),...(g.tags||[]),g.description||''].join(' ').toLowerCase();
      return hay.includes(q);
    });
  }

  function renderCategories(){
    const counts = Object.fromEntries(state.categories.map(c=>[c.id, state.games.filter(g=>g.category===c.id).length]));
    const items=[{id:'all',emoji:'✦',label:'Todos',count:state.games.length},...state.categories.map(c=>({id:c.id,emoji:c.emoji||CATEGORY_EMOJI[c.id],label:catLabel(c.id),count:counts[c.id]||0}))];
    els.categoryStrip.innerHTML=items.map(c=>`<button class="category-chip" type="button" data-category="${c.id}" aria-pressed="${state.category===c.id}"><span>${c.emoji}</span>${escapeHtml(c.label)} <small>${c.count}</small></button>`).join('');
  }

  function renderAll(){
    renderCategories();
    const filtered=matchingGames();
    els.homeGrid.innerHTML=filtered.map(gameCard).join('');
    els.exploreGrid.innerHTML=filtered.map(gameCard).join('');
    els.gameCount.textContent=`${filtered.length} jogos`;
    els.emptyState.hidden=filtered.length>0;
    const featured=FEATURED.map(s=>state.games.find(g=>g.slug===s)).filter(Boolean);
    els.featuredRail.innerHTML=featured.map(gameCard).join('');
    renderFavorites(); renderRecent(); bindCards();
  }

  function renderFavorites(){
    const games=state.games.filter(g=>state.favorites.has(g.slug));
    els.favoritesGrid.innerHTML=games.map(gameCard).join('');
    els.favoritesEmpty.hidden=games.length>0;
  }
  function renderRecent(){
    const bySlug=new Map(state.games.map(g=>[g.slug,g]));
    const games=state.recent.map(s=>bySlug.get(s)).filter(Boolean);
    els.recentGrid.innerHTML=games.map(gameCard).join('');
    els.recentRail.innerHTML=games.slice(0,8).map(gameCard).join('');
    els.recentSection.hidden=games.length===0; els.recentEmpty.hidden=games.length>0;
  }

  function bindCards(){
    document.querySelectorAll('[data-game]').forEach(card=>{
      card.onclick=(ev)=>{ if(ev.target.closest('[data-favorite]')) return; openGame(card.dataset.game); };
    });
    document.querySelectorAll('[data-favorite]').forEach(btn=>{
      btn.onclick=(ev)=>{ ev.stopPropagation(); toggleFavorite(btn.dataset.favorite); };
    });
  }

  function toggleFavorite(slug){
    haptic('light');
    if(state.favorites.has(slug)){ state.favorites.delete(slug); notify('Removido dos favoritos'); }
    else { state.favorites.add(slug); notify('Adicionado aos favoritos'); }
    save(); renderAll();
    if(state.activeGame?.slug===slug) syncPlayerFavorite();
  }

  function addRecent(slug){ state.recent=[slug,...state.recent.filter(s=>s!==slug)].slice(0,30); save(); }
  function syncPlayerFavorite(){ const fav=state.activeGame && state.favorites.has(state.activeGame.slug); els.playerFavorite.textContent=fav?'♥':'♡'; els.playerFavorite.style.color=fav?'#ff8fd7':''; }

  function openGame(slug){
    const game=state.games.find(g=>g.slug===slug); if(!game) return;
    haptic('medium'); state.activeGame=game; addRecent(slug);
    els.playerTitle.textContent=game.name; els.playerCategory.textContent=`${CATEGORY_EMOJI[game.category]||'🎮'} ${catLabel(game.category).toUpperCase()}`;
    els.loader.hidden=false; els.player.hidden=false; document.body.style.overflow='hidden'; syncPlayerFavorite();
    els.frame.src=`/play/${game.path}`;
    try { tg?.BackButton?.show(); tg?.disableVerticalSwipes?.(); tg?.requestFullscreen?.(); } catch {}
    history.pushState({player:slug},'',`#play=${encodeURIComponent(slug)}`);
    renderRecent(); bindCards();
  }

  function closePlayer(){
    if(els.player.hidden) return;
    els.player.hidden=true; els.frame.src='about:blank'; state.activeGame=null; document.body.style.overflow='';
    try { tg?.BackButton?.hide(); tg?.enableVerticalSwipes?.(); if(tg?.isFullscreen) tg.exitFullscreen?.(); } catch {}
    if(location.hash.startsWith('#play=')) history.replaceState({},'',location.pathname+location.search);
  }

  function shareGame(){
    if(!state.activeGame) return;
    haptic('light');
    try { tg?.switchInlineQuery?.(`game:${state.activeGame.slug}`, ['users','groups','channels']); }
    catch { notify('Use o modo inline do bot para compartilhar'); }
  }
  function shareCatalog(){ try { tg?.switchInlineQuery?.('', ['users','groups','channels']); } catch { notify('Abra pelo Telegram para compartilhar'); } }

  function setView(view){
    if(!['home','explore','favorites','recent'].includes(view)) view='home';
    state.currentView=view; document.querySelectorAll('.view').forEach(v=>v.classList.toggle('view--active',v.dataset.view===view));
    document.querySelectorAll('.nav-item').forEach(b=>b.classList.toggle('nav-item--active',b.dataset.viewTarget===view));
    window.scrollTo({top:0,behavior:'smooth'}); haptic('light');
  }

  function openFromStartParam(){
    const params=new URLSearchParams(location.search);
    const raw=tg?.initDataUnsafe?.start_param || params.get('tgWebAppStartParam') || params.get('startapp');
    const hash=location.hash.match(/^#play=([\w-]+)/)?.[1];
    const slug=raw||hash; if(slug && state.games.some(g=>g.slug===slug)) setTimeout(()=>openGame(slug),120);
  }

  function bindUI(){
    els.search.addEventListener('input',()=>{ state.query=els.search.value; els.clearSearch.hidden=!state.query; renderAll(); });
    els.clearSearch.onclick=()=>{ els.search.value=''; state.query=''; els.clearSearch.hidden=true; renderAll(); };
    els.categoryStrip.onclick=(e)=>{ const btn=e.target.closest('[data-category]'); if(!btn)return; state.category=btn.dataset.category; renderAll(); };
    document.querySelectorAll('[data-view-target]').forEach(b=>b.onclick=()=>setView(b.dataset.viewTarget));
    document.querySelectorAll('[data-go]').forEach(b=>b.onclick=()=>setView(b.dataset.go));
    $('randomButton').onclick=()=>{ const pool=matchingGames(); if(pool.length) openGame(pool[Math.floor(Math.random()*pool.length)].slug); };
    $('shareCatalogButton').onclick=shareCatalog; $('playerBack').onclick=closePlayer; $('playerShare').onclick=shareGame;
    $('playerFavorite').onclick=()=>state.activeGame&&toggleFavorite(state.activeGame.slug);
    $('playerReload').onclick=()=>{ if(!state.activeGame)return; const src=els.frame.src; els.loader.hidden=false; els.frame.src='about:blank'; requestAnimationFrame(()=>els.frame.src=src); haptic('light'); };
    els.frame.addEventListener('load',()=>{ if(els.frame.src!=='about:blank') setTimeout(()=>els.loader.hidden=true,180); });
    window.addEventListener('popstate',()=>{ if(!els.player.hidden) closePlayer(); });
    window.addEventListener('online',()=>els.offline.hidden=true); window.addEventListener('offline',()=>els.offline.hidden=false); els.offline.hidden=navigator.onLine;
  }

  async function init(){
    initTelegram(); loadUserData(); bindUI();
    try { await loadCatalog(); }
    catch(err){ console.error(err); notify('Não foi possível carregar o catálogo'); els.emptyState.hidden=false; }
  }
  init();
})();
