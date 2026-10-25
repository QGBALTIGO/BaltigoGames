() => {
  const scene=window.__baltigo.games[0].scene.getScenes(true).find(scene=>scene.player&&typeof scene.targetScore==='number');
  const handle=window.__terminalNative?.handleWin;
  if(!scene||typeof handle!=='function')throw new Error('Space Fighter native completion handler is unavailable');
  scene.score=scene.targetScore;
  // updateGame sets this flag before calling handleWin (mechanics.js:356-358).
  // Omitting it creates a second result panel on the following update.
  scene.hasWon=true;
  handle(scene);
  return {kind:'source-native completion branch',method:'module.handleWin',precondition:'Native score target reached and hasWon set exactly as updateGame does.'};
}
