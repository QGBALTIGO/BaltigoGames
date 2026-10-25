() => {
  const game=window.__baltigo.games[0];
  const scene=game.scene.getScenes(true).find(s=>s.FRUITS?.length&&typeof s.merge==='function');
  if(!scene||!scene.started)throw new Error('Fruit Merge not playing yet');
  const index=scene.FRUITS.length-1;
  const a=scene.createFruit(460,1100,index,false);
  const b=scene.createFruit(620,1100,index,false);
  scene.merge(a,b);
  return {kind:'near-win two final fruits fixture, original merge/tween/completion logic',method:'merge(a,b)',fruit:scene.FRUITS[index].key};
}
