() => {
  const scene=window.__baltigo.games[0].scene.getScenes(true).find(scene=>scene.sys.settings.key==='GameScene');
  if(!scene?.ready || scene.state.finished || !scene.player?.body || !scene.exitDoor?.body)throw new Error('Parkour must be genuinely started with its player and exit');
  scene.player.body.setAllowGravity(false);
  scene.player.setVelocity(0,0);
  scene.player.body.reset(scene.exitDoor.x,scene.exitDoor.y);
  return {kind:'near-win real source exit-door overlap',condition:'Actual player reaches the real exit above its lip; registered physics handler finishes gameplay and starts the source WinScene, exercising real teardown'};
}
