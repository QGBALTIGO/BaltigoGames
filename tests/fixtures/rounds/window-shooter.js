() => {
  const scene = window.__baltigo.games[0].scene.getScene('GameScene');
  if (!scene.sys.isActive() || !scene.isActive) throw new Error('Source gameplay has not started');
  scene.kills = 9;
  scene.activeTimer?.remove();
  scene.activeCharIdx = 1;
  scene.currentCharType = 'terrorist';
  const target = scene.windowRects[1];
  // Source-native last-hit branch; the actual UI buttons below use browser gestures.
  scene.handleTap({x:target.x * scene.sys.game.canvas.width / 1920,y:target.y * scene.sys.game.canvas.height / 1080});
  return {kind:'source-native last-hit branch fixture', method:'GameScene.handleTap(last terrorist)', scope:'Near-win branch, not a complete human playthrough'};
}
