"""Reproducible Portuguese game metadata and reviewed source-text dictionary."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Each line follows registry order, keeping the source identifier stable.
METADATA = """2048|Deslize as peças e junte números iguais até chegar a 2048.
6 octógonos|Deslize as peças octogonais e encontre a combinação correta.
Pedra, papel e tesoura|Escolha sua jogada e vença o computador.
Sudoku|Complete o tabuleiro sem repetir números nas linhas, colunas e regiões.
Abhita|Mova seu personagem e desvie dos obstáculos.
Batalha alienígena|Enfrente invasores e sobreviva aos ataques.
Antigravidade|Inverta a gravidade para atravessar os obstáculos.
Arqueiro|Arraste para mirar e solte para disparar a flecha.
Torre em equilíbrio|Empilhe os blocos sem derrubar a torre.
Basquete|Mire e arremesse a bola para acertar a cesta.
Caça aos pássaros|Acompanhe os alvos em movimento e acerte seus disparos.
Explosão em cadeia|Lance a bomba perto dos inimigos e aproveite a explosão.
Pontos explosivos|Toque no momento certo para acertar o próximo alvo.
Boliche|Mire, solte a bola e derrube os pinos.
Quebra-blocos|Mova a plataforma, rebata a bola e destrua os blocos.
Estoura-bolhas|Encontre grupos de bolhas iguais e marque pontos.
Lança-bolhas|Mire e junte três ou mais bolhas da mesma cor.
Esmaga-insetos|Toque nos insetos antes que eles escapem.
Mistura perfeita|Segure os ingredientes para preparar a receita na proporção correta.
Doces combinados|Troque doces vizinhos para formar combinações de três ou mais.
Explosão de doces|Combine peças iguais para marcar pontos.
Canhão de precisão|Ajuste a mira e a força para acertar os alvos.
Empilha-cargas|Solte as caixas do guindaste e construa uma pilha estável.
Corrida no trânsito|Troque de faixa, evite os carros e recolha moedas.
Carrom|Arraste o disco para mirar e encaçapar suas peças.
Xadrez|Jogue com as peças brancas e dê xeque-mate no computador.
Caminho circular|Toque na hora certa para seguir o percurso.
Acenda a lâmpada|Gire as conexões e complete o circuito elétrico.
Pegue-me se puder|Corra pela arena e escape dos perseguidores.
Colecionador|Recolha os itens antes que o tempo termine.
Passagem das cores|Mude de faixa e atravesse apenas barreiras da sua cor.
Mistura de cores|Despeje os líquidos até deixar cada frasco com uma única cor.
Conectados|Ligue os pontos iguais sem cruzar os caminhos.
Cozinha expressa|Arraste os ingredientes na ordem certa para preparar o pedido.
Aventura nas plataformas|Corra e salte para evitar perigos e alcançar a saída.
Limpeza cósmica|Mova a nave, recolha destroços e economize bateria.
Críquete 1-2-3|Rebata a bola no momento certo.
Travessia movimentada|Atravesse ruas e rios sem colidir com os obstáculos.
Controle da multidão|Guie o grupo e escolha passagens que aumentam sua equipe.
Cobra em curvas|Toque para mudar de direção, recolha pontos e evite seu rastro.
Corte a corda|Corte as cordas para levar o doce até o destino.
Torre dos demônios|Ataque os inimigos e avance pelas escadas.
Rei dos desafios|Salte entre os perigos até alcançar o objetivo.
Desvie dos inimigos|Mova-se entre os ataques e sobreviva.
Mestre dos desvios|Desvie dos obstáculos enquanto a velocidade aumenta.
Salto nas alturas|Vá de plataforma em plataforma e desvie dos inimigos.
Tecelão dos sonhos|Fique parado para criar pontes e atravesse antes que elas desabem.
Ellars|Observe os obstáculos e reaja a tempo para sobreviver.
Máfia sem fim|Mire nos inimigos e recolha suas recompensas.
Corrida infinita|Continue correndo e desvie de todos os obstáculos.
Fúria aérea|Pilote seu caça e sobreviva ao combate.
Caça de combate|Desvie dos ataques e dispare contra os inimigos.
Voo entre os canos|Toque para ganhar altura e evite os canos.
Salto invertido|Toque para mudar de lado e aterrissar com segurança.
Macaco voador|Atravesse a floresta e alcance o próximo apoio.
Futebol de cabeças|Mova, salte e chute para marcar mais gols que o adversário.
Corrida na floresta|Salte sobre troncos e espaços vazios durante a corrida.
Quatro pontos|Observe o padrão e toque nos pontos na ordem correta.
Cesta de frutas|Mova a cesta para recolher frutas e evite as bombas.
Frutas cósmicas|Corte as frutas para marcar pontos e evite os perigos.
Fusão de frutas|Solte frutas iguais para combiná-las e criar novas peças.
Salto luminoso|Mova-se, carregue o salto e solte para alcançar a próxima plataforma.
Ponte de vidro|Escolha a plataforma segura e chegue ao final sem cair.
Duelo de pistoleiros|Espere a mira se alinhar e dispare no momento certo.
Corrida armada|Avance, salte e dispare contra os inimigos.
Blocos hexagonais|Arraste as peças para completar linhas no tabuleiro.
Fome de aventura|Recolha comida e evite os obstáculos.
Ponto saltador|Toque para saltar sobre os perigos em movimento.
Gigante na cidade|Ataque construções, desvie dos projéteis e sobreviva.
Reflexo a laser|Gire os espelhos para levar o laser até todos os alvos.
Ligue os pares|Conecte peças iguais pelo caminho mais curto.
Ludo|Lance o dado e leve todas as peças até a chegada.
Aventura do encanador|Mova-se e salte pelas plataformas até alcançar a bandeira.
Desafio de matemática|Resolva as contas antes que o tempo termine.
Jogo da memória|Vire duas cartas e encontre todos os pares.
Cartas da memória|Memorize as posições e combine as cartas iguais.
Fusão de números|Junte números iguais e alcance a maior pontuação.
Um carro|Troque de faixa para desviar do trânsito.
Defesa orbital|Defenda a estação e destrua os meteoros.
Come-pontos|Recolha todos os pontos do labirinto e evite os fantasmas.
Pares rápidos|Observe os pares e encontre as combinações corretas.
Parkour|Salte entre as plataformas e atravesse os obstáculos.
Encontre a saída|Recolha as chaves e atravesse o labirinto antes do tempo acabar.
Quadrado perfeito|Segure para aumentar o quadrado e solte no tamanho certo.
Piratas|Navegue e enfrente os perigos dos mares.
Explorador de planetas|Explore o cenário e fotografe as plantas sem se aproximar dos animais.
Guerra planetária|Proteja seu planeta dos invasores espaciais.
Desvio de projéteis|Evite os disparos e ataque os adversários.
Perguntas e respostas|Escolha a resposta correta para avançar e marcar pontos.
Sinal verde, sinal vermelho|Segure para avançar no verde e pare no vermelho.
Atravesse a rua|Toque ou deslize para atravessar o trânsito com segurança.
Corrida de rua|Pilote entre os carros e evite as colisões.
Destruição de robôs|Desvie dos foguetes e destrua os robôs.
Mestre dos parafusos|Solte os parafusos e organize as peças.
Corredor das sombras|Escape das sombras e recolha fragmentos de luz.
Atirador das sombras|Mire e elimine os inimigos sem ser atingido.
Coletor de formas|Recolha apenas a forma indicada e evite as demais.
Encaixe as formas|Arraste cada peça para o contorno correspondente.
Alvos inimigos|Dispare contra os inimigos antes que eles alcancem o outro lado.
Arena de tiro|Mova-se pela arena e sobreviva aos ataques.
Circuito de sinais|Gire as peças para conectar o início ao fim do circuito.
Rumo ao céu|Suba pelas plataformas e evite cair.
Quebra-cabeça deslizante|Mova as peças vizinhas ao espaço vazio para ordenar a imagem.
Cobrinha|Deslize para guiar a cobra, comer e crescer sem colidir.
Cobras e escadas|Lance o dado e alcance a casa 100.
Atirador de precisão|Arraste a mira e dispare quando o alvo ficar vermelho.
Combate espacial|Pilote entre asteroides e enfrente os inimigos.
Astronauta|Mova-se pelo espaço e recolha peças da nave.
Ondas espaciais|Segure para subir, solte para descer e permaneça na passagem.
Quadrado inicial|Toque nas peças para deixar todo o tabuleiro com a mesma cor.
Torre de blocos|Solte os blocos no momento certo para empilhar o mais alto possível.
Ponte de palitos|Segure para esticar a ponte e solte para atravessar.
Lance os palitos|Lance os palitos no alvo sem acertar os que já estão presos.
Corrida direta|Reaja aos obstáculos durante a corrida.
Corrida pela sobrevivência|Continue avançando e escape dos perigos.
Sobrevivente|Mova-se pela arena e sobreviva às ondas de inimigos.
Tênis de mesa|Mova a raquete e rebata a bola para marcar pontos.
Toque no alvo|Toque nos alvos antes que eles desapareçam.
Arremesso certeiro|Carregue a força e solte para atingir o objetivo.
Tetris|Mova e gire as peças para completar linhas horizontais.
O mesmo nível 1|Descubra o truque da fase e abra a porta.
O mesmo nível 2|Observe o cenário e encontre uma nova forma de abrir a porta.
O mesmo nível 3|Resolva o desafio da fase para alcançar a saída.
O mesmo nível 4|Teste os mecanismos do cenário e encontre a solução.
O mesmo nível 5|Desvende a armadilha e complete o desafio.
Deus do trovão|Use os raios para enfrentar os inimigos.
Jogo da velha|Forme uma linha com três símbolos antes do adversário.
Teclas rápidas|Toque apenas nas peças escuras e não deixe nenhuma passar.
Defesa da torre|Proteja a torre das ondas de inimigos.
Defesa da trincheira|Resista ao ataque e mantenha sua posição.
Dois carros|Controle os dois veículos, recolha os círculos e desvie dos quadrados.
Dois carros: desafio|Alterne os carros para recolher os itens e evitar obstáculos.
Reino imprevisível|Escolha as decisões do rei e mantenha os recursos em equilíbrio.
Defesa antiviral|Mova-se, dispare contra os vírus e recolha vacinas.
Acerte o inseto|Toque nos insetos que surgem dos buracos para marcar pontos.
Palavra do dia|Descubra a palavra de cinco letras em até seis tentativas.
Roda de palavras|Ligue as letras para completar todas as palavras do tabuleiro.
Disputa de pênaltis|Escolha a direção para chutar e defender em cinco rodadas.
Ataque silencioso|Deslize para se mover e ataque os inimigos pelas costas.
Plataformas traiçoeiras|Descubra as armadilhas para chegar à saída.
Prenda o ponto|Trace um caminho e impeça o ponto de escapar.
Atirador na janela|Acerte os inimigos e proteja os reféns."""


def main():
    registry = json.loads((ROOT / 'data/registry.json').read_text(encoding='utf-8'))
    lines = METADATA.strip().splitlines()
    assert len(lines) == len(registry['games']), (len(lines), len(registry['games']))
    entries = {}
    dictionary = {}
    for game, line in zip(registry['games'], lines, strict=True):
        name, description = line.split('|', 1)
        entries[game['slug']] = {'name': name, 'description': description,
                                 'tutorial': description, 'language': 'pt-BR'}
        dictionary[game['name']] = name
        dictionary[game['description']] = description
    # Several upstream folder/catalog names describe a different game. These
    # descriptions follow the actual loaded scene, controls and objectives.
    corrections = {
        '6oct': ('Letras do deserto', 'Toque nas letras para formar palavras e complete o tabuleiro. Use Misturar para reorganizar e Limpar para apagar.', 'word-quiz'),
        'abhita': ('Peças na grade', 'Arraste as peças para a grade e complete o quebra-cabeça.', 'puzzle'),
        'cricket-123': ('Maquinista', 'Use Direita para acelerar e Esquerda para frear. Pare nas estações, abra as portas com Ação e respeite os sinais vermelhos.', 'casual'),
        'four-dots': ('Quatro em linha', 'Escolha uma coluna para soltar a peça. Alinhe quatro peças na horizontal, vertical ou diagonal antes do computador.', 'board'),
        'road-fighter': ('Desafio na corda', 'Toque nos lados para mudar de posição. Use Ação para atravessar espaços apertados, recolha pontos e sobreviva até o tempo acabar.', 'arcade'),
        'thunder-god': ('Labirinto fantasma', 'Recolha todas as chaves e alcance a saída. Use as setas para mover e Ação para avançar rapidamente entre os perigos.', 'arcade'),
        'tower-shooter': ('Fuga da torre', 'Mova-se e salte para subir a torre que está desabando. Evite inimigos e espinhos e recolha gemas.', 'platformer'),
        'survival-run': ('Portais assombrados', 'Encontre os portais do labirinto e use Ação para girar as runas. Feche todos os portais antes que o tempo acabe e evite os fantasmas.', 'puzzle'),
        'straight-rush': ('Disparo de precisão', 'Segure para carregar a força e solte para lançar. Recolha moedas e evite os inimigos.', 'arcade'),
        'jump-dot': ('Salto lateral', 'Toque à esquerda ou à direita para trocar de posição e evitar os obstáculos.', 'arcade'),
        'collector': ('Pouso de precisão', 'Use o controle para mover para os lados, evitar obstáculos e alcançar uma aterrissagem segura.', 'arcade'),
        'shoot-enemy': ('Mira carregada', 'Arraste o controle para mirar, segure para carregar a força e solte para disparar.', 'shooter'),
        'level-devil': ('Túnel de obstáculos', 'Avance pelo túnel e desvie dos obstáculos para percorrer a maior distância.', '3d'),
        'line-trap': ('Defesa por linhas', 'Desenhe linhas para bloquear os inimigos e proteger o núcleo.', 'puzzle'),
        'chess': ('Xadrez', 'Xadrez casual com regras simplificadas. Jogue com as brancas e dê xeque-mate no computador.', 'board'),
    }
    for slug, (name, description, category) in corrections.items():
        entries[slug].update(name=name, description=description, tutorial=description, category=category)
        original = next(game for game in registry['games'] if game['slug'] == slug)
        dictionary[original['name']] = name
        dictionary[original['description']] = description
    controls = {
        '2048':'Deslize para cima, baixo ou para os lados para mover todas as peças. No computador, use as setas.',
        'tetris':'Deslize para os lados para mover. Toque no botão de giro e use Baixo para acelerar ou Soltar para encaixar a peça.',
        'car-race':'Deslize para os lados para trocar de faixa. No computador, use as setas ou A e D.',
        'snake':'Deslize na direção desejada para guiar a cobra. Evite as paredes e o próprio corpo.',
        'chess':'Toque em uma peça branca e depois em uma casa destacada para mover. Versão casual: não há roque, captura de passagem ou empates por repetição e regra dos 50 lances. A promoção para dama é automática.',
        'sudoku':'Toque em uma casa e depois no número desejado. Use Limpar casa para apagar sua escolha.',
        'rock-paper-scissors':'Toque em Pedra, Papel ou Tesoura antes que a contagem termine.',
        'archer':'Toque e arraste para puxar o arco. Solte para disparar na direção da mira.',
        'basketball':'Arraste a partir da bola para ajustar a direção e a força. Solte para arremessar e aguarde a bola parar.',
        'bowling':'Arraste a bola para ajustar a mira e solte para lançar. Você tem dois lançamentos por rodada.',
        'bomb-blast':'Deslize para os lados para lançar a bomba à faixa vizinha. Solte-a perto dos inimigos antes que exploda.',
        'boom-dots':'Toque para lançar o personagem contra o alvo em movimento. Acerte três vezes e evite cinco erros.',
        'breakoid':'Deslize para mover a plataforma sob a bola. Rebata a bola para quebrar os blocos.',
        'bubble-shooter':'Deslize para mirar e toque para disparar. Junte ao menos três bolhas iguais.',
        'bug-smasher':'Toque diretamente nos insetos antes que eles escapem.',
        'buttermilk':'Segure um ingrediente para despejar, solte para parar e deslize para baixo no copo para servir.',
        'candy-crush':'Arraste uma peça até uma vizinha para trocar suas posições e formar uma linha de três ou mais.',
        'candy-crusher':'Arraste as peças para formar linhas de três ou mais iguais.',
        'cargo-stack':'Toque na tela para soltar a caixa do guindaste. Espere o alinhamento antes de tocar.',
        'carrom':'Arraste para trás a partir do disco para ajustar mira e força. Solte para lançar.',
        'circle-path':'Toque quando a bola em movimento estiver sobre o próximo alvo.',
        'color-dash':'Toque em Esquerda e Direita para mudar de faixa. Passe apenas por barreiras da sua cor.',
        'colour-pour':'Toque no frasco de origem e depois no de destino. Só despeje sobre uma cor igual ou em um frasco vazio.',
        'cooking':'Arraste os ingredientes da mesa para o prato na ordem indicada pelo pedido.',
        'cricket-123':corrections['cricket-123'][1],
        'cool-platformer':'Use os botões Esquerda, Direita e Ação para se mover com as rajadas de vento. No computador, use as setas.',
        'cut-rope':'Deslize sobre uma corda para cortá-la. Observe o balanço e faça o doce alcançar o destino.',
        'demon':'Use os controles de direção para mover, Saltar para pular e Ação para atacar. Suba pelas escadas após eliminar os inimigos.',
        'doodle-jump':'Toque nos lados da tela para direcionar os saltos entre as plataformas.',
        'four-dots':corrections['four-dots'][1],
        'fruit-basket':'Arraste a cesta para os lados. Recolha frutas e evite as bombas.',
        'fruit-cosmics':'Deslize sobre as frutas para cortá-las. Evite os objetos perigosos.',
        'fruit-merge':'Mova o ponto de lançamento e toque para soltar uma peça. Duas peças iguais se combinam.',
        'glass-step':'Toque na plataforma escolhida para saltar. Apenas um dos vidros de cada passo é seguro.',
        'gunman':'Toque ou clique quando a linha de mira apontar para o inimigo.',
        'hex-puzzle':'Arraste uma peça da bandeja para o tabuleiro. Complete linhas para abrir espaço.',
        'jump-dot':corrections['jump-dot'][1],
        'kaiju-krush':'Segure os botões Esquerda e Direita para mover e toque em Atacar para golpear.',
        'link':'Arraste a partir de um ponto até outro da mesma cor. Preencha o tabuleiro sem cruzar os caminhos.',
        'math-quest':'Leia a conta e toque na alternativa correta. Acerte para subir até o objetivo.',
        'memory':'Toque em duas cartas para virá-las. Memorize as posições para encontrar todos os pares.',
        'memory-cards':'Toque nas cartas, duas por vez, para revelar e combinar os personagens iguais.',
        'pairing':'Memorize os pares do guia e toque nos itens correspondentes dentro do tempo.',
        'pathfinder':'Use as setas ou os botões na tela para mover, recolher as chaves e chegar à saída.',
        'perfect-square':'Toque e segure para aumentar o quadrado. Solte no tamanho certo para cair entre as paredes.',
        'quiz':'Leia a pergunta e toque em uma das alternativas. A resposta correta aparece após a escolha.',
        'red-light-green-light':'Segure a tela para avançar no sinal verde. Solte e fique parado assim que o sinal ficar vermelho.',
        'road-cross':'Toque ou deslize para avançar e atravessar as ruas sem colidir.',
        'road-fighter':corrections['road-fighter'][1],
        'shape-collector':'Use Esquerda e Direita para mover e recolha apenas a forma destacada na meta.',
        'shape-fitter':'Arraste cada forma para o contorno que corresponde a ela.',
        'slide-puzzle':'Toque em uma peça vizinha ao espaço vazio para movê-la. Repita até ordenar a imagem.',
        'sniper':'Arraste a mira sobre o alvo. Toque para disparar quando a mira ficar vermelha.',
        'space-waves':'Segure para subir e solte para descer. Continue dentro da passagem.',
        'stack-tower':'Toque para soltar o bloco em movimento. Apenas a parte alinhada com a torre permanece.',
        'stick-game':'Toque e segure para esticar a ponte. Solte quando ela tiver o comprimento adequado.',
        'stick-toss':'Toque para lançar um palito. Evite acertar os que já estão presos ao alvo.',
        'tap-target':'Toque em cada alvo antes que ele desapareça.',
        'tic-tac-toe':'Toque em uma casa vazia para jogar. Alinhe três símbolos para vencer.',
        'tile-tap':'Toque apenas nas peças escuras, na ordem em que chegam.',
        'whack-a-bug':'Toque nos insetos que surgirem dos buracos. Evite os alvos que reduzem seus pontos.',
        'wordle':'Toque nas letras do teclado e depois em ENVIAR. Use palavras portuguesas de cinco letras, sem acentos. Verde indica posição correta; amarelo indica outra posição.',
        'words-of-wonder':'Arraste pelas letras da roda, em sequência, e solte para confirmar uma palavra portuguesa.',
        '6oct':corrections['6oct'][1],
        'penalty':'Escolha Esquerda, Centro ou Direita e toque em Ação para chutar. Na defesa, escolha um lado e use Ação para saltar.',
        'swipe-assassin':'Deslize para mover. Ataque cada inimigo pelas costas e evite seu campo de visão.',
        'window-shooter':'Toque nos inimigos para disparar. Não acerte os reféns.',
        'level-devil':'Segure os botões Esquerda e Direita para desviar no túnel. No computador, use as setas ou A e D. O avanço é automático.',
        'crossy-road':'Toque nas quatro setas da tela para avançar, voltar ou mover para os lados. Atravesse sem colidir com o trânsito.',
        'curve-snake':'Os toques alternam entre seguir reto, virar à direita e virar à esquerda. No computador, pressione Espaço para fazer o mesmo.',
        'vaccine-shooter':'Use Esquerda e Direita para mover e segure Ação para atirar. Dê dois toques em Ação para usar a rajada quando tiver vacinas.',
        'shadow-runner':'Use o controle virtual para fugir e recolha fragmentos de luz. Toque em Ação para usar uma explosão de luz e eliminar as sombras, gastando uma carga.',
        'line-trap':'Toque, arraste e solte para desenhar uma barreira. Intercepte os inimigos antes que eles alcancem o núcleo.',
    }
    for slug, text in controls.items():
        entries[slug]['controls_pt'] = text
    orientations = ROOT / 'data/game-orientations.json'
    if orientations.exists():
        for slug, values in json.loads(orientations.read_text(encoding='utf-8')).items():
            if slug in entries:
                entries[slug].update(values)
    (ROOT / 'data/catalog-pt.json').write_text(json.dumps(entries, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    target = ROOT / 'data/localization-pt.json'
    existing = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    existing.update(dictionary)
    dictionary = existing
    target.write_text(json.dumps(dictionary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
