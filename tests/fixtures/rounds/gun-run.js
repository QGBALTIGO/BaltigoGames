() => {
  const scene=window.__baltigo.games[0].scene.getScenes(true)[0];
  if(!scene.gameStarted || !scene.hero?.body || !scene.portal?.body)throw new Error('Gun Run must be genuinely started with hero and final portal');
  scene.hero.body.setAllowGravity(false);
  scene.hero.setVelocity(0,0);
  const camera=scene.cameras.main;
  const center=scene.portal.getCenter();
  camera.setScroll(Math.max(0,Math.min(camera.getBounds().width-camera.width,center.x-camera.width/2)),0);
  scene.hero.body.reset(center.x,center.y);
  return {kind:'near-win real source portal overlap',condition:'Actual hero reaches the actual final portal; the registered source physics handler destroys its body and opens the native result'};
}
