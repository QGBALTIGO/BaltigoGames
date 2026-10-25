() => {
  const game=window.__baltigo.games[0];
  const scene=game.scene.getScenes(true).find(scene=>typeof scene.createWinOverlay==='function');
  if(!scene)throw new Error('Straight Rush gameplay scene is not active');
  scene.score=scene.targetScore;
  scene.updateHud();
  scene.createWinOverlay();
  return {kind:'source-native completion branch',method:scene.sys.settings.key+'.createWinOverlay',precondition:'Score equals the authored target; createWinOverlay owns gameWon and input cleanup.'};
}
