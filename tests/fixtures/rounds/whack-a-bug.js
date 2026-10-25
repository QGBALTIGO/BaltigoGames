() => {
  const scene = window.__baltigo.games[0].scene.getScene('GamePlayScene');
  if (scene.isPaused) throw new Error('The real start gesture has not resumed the source game');
  scene.score = scene.scoreTarget;
  scene.remainingTime = Math.max(1, scene.remainingTime);
  window.__terminalNative.showGameOver(scene);
  return {kind:'source-native result branch fixture', method:'module.showGameOver(score >= scoreTarget)', scope:'Result and real Next/Replay controls; not a complete gameplay victory'};
}
