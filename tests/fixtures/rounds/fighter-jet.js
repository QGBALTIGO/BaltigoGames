() => {
  const scene=window.__baltigo.games[0].scene.getScenes(true)[0];
  const enemy=scene.terrorists?.getChildren().find(item=>item.active);
  if(!enemy)throw new Error('No authored terrorist target available');
  scene.score=Math.max(0,Number(scene.requiredKills)-1);
  enemy.setVelocity(0,0);
  const missile=scene.missiles.create(enemy.x,enemy.y,'missile');
  missile.body.setAllowGravity(false);
  missile.setVelocity(0,0);
  return {kind:'near-win real source physics overlap',condition:'One actual missile overlaps the final actual terrorist; source collision reaches requiredKills and opens its native result'};
}
