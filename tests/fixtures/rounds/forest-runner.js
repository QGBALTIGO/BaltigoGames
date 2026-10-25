() => {
  const scene=window.__baltigo.games[0].scene.getScenes(true)[0];
  scene.reachGoal(scene.player,null);
  return {kind:'source-native goal completion branch',method:'GameScene.reachGoal',note:'Includes the real gameOver flag before the result panel; calling the panel builder alone leaves the camera moving'};
}
