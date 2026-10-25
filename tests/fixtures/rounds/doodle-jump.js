() => {
  const game=window.__baltigo.games[0];
  const scene=game.scene.getScenes(true).find(s=>s.doodler&&Number.isFinite(s.targetScore));
  if(!scene||scene.startgamenow!==1||typeof window.__terminalNative?.updateScore!=='function')throw new Error('Doodle Jump requires its genuine Play gesture first');
  scene.doodler.body.allowGravity=false;
  scene.doodler.setVelocity(0,0);
  scene.score=Math.max(0,scene.targetScore-1);
  scene.initialDoodlerY=scene.doodler.y+scene.targetScore*10+1;
  window.__terminalNative.updateScore(scene,scene.config);
  return {kind:'controlled near-win height fixture, original height-scoring callback',method:'updateScore(scene,config)',target:scene.targetScore};
}
