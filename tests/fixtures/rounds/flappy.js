() => {
  const game=window.__baltigo.games[0];
  const scene=game.scene.getScenes(true).find(s=>Number.isFinite(s.targetscore));
  if(!scene||typeof window.__terminalNative?.updateScore!=='function')throw new Error('Flappy native scoring callback not ready');
  if(!scene.isGameStarted || scene.gameOver || scene.levelClearedTriggered || !scene.bird?.body)throw new Error('Flappy scoring fixture requires a genuinely active living bird');
  if(scene.bird?.body){scene.bird.body.allowGravity=false;scene.bird.setVelocity(0,0);}
  scene.score=Math.max(0,scene.targetscore-1);
  scene.levelClearedTriggered=false;
  window.__terminalNative.updateScore(scene,scene.config);
  return {kind:'near-win score fixture, source-native pipe scoring callback',method:'updateScore(scene,config)',target:scene.targetscore,live_round_required:true};
}
