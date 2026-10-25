() => {
  const scene=window.__baltigo.games[0].scene.getScenes(true).find(s=>s.doodler&&Number.isFinite(s.targetScore));
  if(!scene||scene.startgamenow!==1||scene.gameOver||!scene.doodler.body||typeof window.__terminalNative?.gameOverHandler!=='function')throw new Error('Doodle Jump Replay requires a live source round');
  window.__terminalNative.gameOverHandler(scene,scene.config);
  return {kind:'source-native loss branch fixture',method:'gameOverHandler(scene,config)',evidence:'The victory screen authors only Next; Replay belongs to the genuine loss screen',live_round_required:true};
}
