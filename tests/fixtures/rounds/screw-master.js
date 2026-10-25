() => {
  const scene=window.__baltigo.games[0].scene.getScenes(true).find(scene=>scene.rowData?.[0]);
  if(!scene||scene.gameOver)throw new Error('A live native tile round is required');
  // Exercise the exact terminal branch used by a white-tile error or timeout.
  // Full real black/white tile input is separately proved by prove_screw_native.
  scene.endGame();
  return {kind:'source-native terminal loss branch',method:'GameScene.endGame',next_applicable:false,unused_WinScene:false};
}
