() => {
  const scene=window.__baltigo.games[0].scene.getScenes(true)[0];
  if(!scene.isGameStarted || !scene.player?.body || !scene.door?.body)throw new Error('Sky High must be genuinely started with its player and door');
  scene.hasKey=true;
  scene.player.body.setAllowGravity(false);
  scene.door.body.setAllowGravity(false);
  scene.door.setVelocity(0,0);
  // Teleporting a near-win fixture must also prepare the real camera's
  // already-traversed position before its collision builds the result panel.
  const camera=scene.cameras.main;
  camera.setScroll(Math.max(0,Math.min(scene.worldWidth-camera.width,scene.door.x-camera.width/2)),0);
  scene.player.body.reset(scene.door.x,scene.door.y);
  scene.player.setVelocity(0,0);
  return {kind:'near-win real source door overlap',condition:'Actual player overlaps the actual final door with the collected-key condition prepared; the registered source physics handler sets levelComplete before destroying the player'};
}
