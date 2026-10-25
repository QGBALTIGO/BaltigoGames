"""Build reviewed in-game translations from the public source text inventory."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEWED = r"""
Score: |Pontos: 
Game Over|Fim de jogo
How to Play|Como jogar
Level Completed|Fase concluída
PLAY|JOGAR
NEXT|CONTINUAR
SURVIVE 60 SECONDS.|SOBREVIVA POR 60 SEGUNDOS.
Final Score: |Pontuação final: 
Score|Pontos
Try Again!|Tente novamente!
You Win!|Você venceu!
Target|Meta
GAME OVER|FIM DE JOGO
Score: 0|Pontos: 0
HOW TO PLAY|COMO JOGAR
Level Complete|Fase concluída
Time: |Tempo: 
Level Complete!|Fase concluída!
YOU WIN!|VOCÊ VENCEU!
Your Score|Seus pontos
Time Left|Tempo restante
Start|Jogar
How To Play|Como jogar
Restart|Reiniciar
Next|Continuar
Unlock the door to finish\nthe level. For hints, tap\nthe bulb.|Abra a porta para concluir\na fase. Para obter uma dica,\ntoque na lâmpada.
LEVEL COMPLETED|FASE CONCLUÍDA
Level Completed!|Fase concluída!
How to play|Como jogar
Carbon dioxide|Dióxido de carbono
Target: |Meta: 
Your Score:|Seus pontos:
Tap to Start|Toque para jogar
LEVEL COMPLETE|FASE CONCLUÍDA
Instructions here.|Veja as instruções para jogar.
Your Turn|Sua vez
Moves: 0|Jogadas: 0
Points: |Pontos: 
Window Shooter|Atirador na janela
Plain and Simple|Simples assim
Are you kidding me?\nJust stand on the button|É sério?\nBasta ficar sobre o botão.
Game Over!|Fim de jogo!
Swipe left or right to move\nthe hero.\nTap the fire button to\nshoot lasers and break\nasteroids.|Deslize para a esquerda ou direita\npara mover o personagem.\nToque no botão de tiro para\ndisparar lasers e destruir\nos asteroides.
Keys: |Chaves: 
SCORE: |PONTOS: 
Moves: |Jogadas: 
Connect four pieces vertically, horizontally or diagonally. The first one to align 4 pieces wins!|Conecte quatro peças na vertical, na horizontal ou na diagonal. Quem alinhar quatro primeiro vence!
Play Again|Jogar novamente
Time: 00:00|Tempo: 00:00
Too many mistakes!|Muitos erros!
START|JOGAR
Swipe left/right to move, swipe down or tap ▼ to fall faster, tap ⟳ to rotate, tap ⏬ to drop. Reach TARGET points to win.|Deslize para os lados para mover. Deslize para baixo ou toque em ▼ para acelerar. Toque em ⟳ para girar e em ⇓ para soltar. Alcance TARGET pontos para vencer.
Try Again|Tentar novamente
Position: |Posição: 
AI Turn|Vez do computador
Tap when the moving ball\nis over the next target.\n\nMiss a tap and you lose!|Toque quando a bola em movimento\nestiver sobre o próximo alvo.\n\nSe errar o momento, você perde!
Hit these to gain\npoints.|Acerte estes itens\npara ganhar pontos.
Avoid hitting this as it\nsteals your score.|Evite este item:\nele reduz seus pontos.
GAME PAUSED|JOGO PAUSADO
Click to Resume|Toque para continuar
Hex Puzzle|Blocos hexagonais
Frame / Rolls|Rodada / Lançamentos
You Win! 🎉|Você venceu!
🎉 YOU WIN|VOCÊ VENCEU
You Lose!|Você perdeu!
Miss: |Erros: 
Light: |Luz: 
Your Score: |Seus pontos: 
Kills: |Eliminações: 
Tap to shoot enemies before they reach the other end.|Toque para atirar nos inimigos antes que eles cheguem ao outro lado.
Time Left:|Tempo restante:
Label: value|Indicador: valor
Light Collected: |Luz recolhida: 
Time’s Up!|O tempo acabou!
Tap to rotate:|Toque para girar:
Perfect Pour!|Mistura perfeita!
You Win!!|Você venceu!
YOUR TURN|SUA VEZ
🎉 You Win!|Você venceu!
💀 You Lose|Você perdeu
Embark on a memory matching journey with your favorite Bleach characters. Test your memory skills and match the pairs to progress through the game!|Encontre os pares dos personagens de Bleach e teste sua memória para avançar no jogo!
Best: |Recorde: 
Time's up!|O tempo acabou!
Complete the circuit from start to end, before time’s up!|Complete o circuito do início ao fim antes que o tempo acabe!
Time Taken|Tempo utilizado
Tap to Play|Toque para jogar
Reach TARGET score to win!|Alcance TARGET pontos para vencer!
Great job reaching the target score!|Parabéns! Você alcançou a meta de pontos!
Tap Replay to play again|Toque em Jogar novamente para recomeçar
Tap any control or press P|Toque em um controle ou pressione P
Tap to Restart|Toque para reiniciar
Cores Collected|Núcleos recolhidos
Time Left: |Tempo restante: 
Level Cleared|Fase concluída
Swipe to aim, tap to shoot.\n\nMatch 3+:|Deslize para mirar e toque para atirar.\n\nCombine três ou mais:
On a grid covered with\nvarious objects, try to form\nhorizontal or vertical chains\nof at least three identical\nones by swapping\nneighbouring objects.|Troque peças vizinhas para formar\nlinhas horizontais ou verticais\ncom pelo menos três peças\niguais no tabuleiro.
Level|Nível
Target Left:|Meta restante:
Tap “Play” to start — You are White|Toque em Jogar para começar. Você joga com as brancas.
⏳ Timeout! You Lose!|O tempo acabou! Você perdeu!
✨ Draw!|Empate!
🔥 You Win!|Você venceu!
💀 You Lose!|Você perdeu!
Drag and drop pieces to the grid below!\nSolve the puzzle to win.|Arraste e solte as peças no tabuleiro!\nResolva o quebra-cabeça para vencer.
Time: 1:00|Tempo: 1:00
Bomb Master!|Mestre das bombas!
Tap to launch the player upward.\nHit the moving enemy.\nClose hits give bonus points!\nWin at 3 hits.\nGame over after 5 misses.|Toque para lançar o personagem.\nAcerte o inimigo em movimento.\nAcertos próximos rendem bônus!\nAlcance três pontos.\nA partida termina após cinco erros.
Swipe to guide your player\nthrough series of obstacles\nthat increase or decrease\nits numbers. The higher\nyour number, the further\nyou go!|Deslize para guiar seu grupo\npor passagens que aumentam\nou diminuem sua equipe.\nQuanto maior o grupo,\nmais longe você chega!
Tap / Click / Space to toggle turn|Toque, clique ou pressione Espaço para mudar de direção
RETRY|TENTAR NOVAMENTE
Lives: |Vidas: 
Money: |Dinheiro: 
Take aim, shoot the mafia,\nand collect their loot.|Mire, atire nos inimigos\ne recolha suas recompensas.
Steps Crossed|Passos concluídos
Tap left or right to switch positions.|Toque à esquerda ou à direita para trocar de posição.
Tap left/right to move. Hold JUMP or press SPACE to charge, release to bounce!|Toque nos lados para mover. Segure SALTAR ou Espaço para carregar e solte para saltar!
GREEN LIGHT|SINAL VERDE
Parts Collected|Peças recolhidas
You did not complete target|Você não alcançou a meta
Word & Quiz|Palavras e perguntas
Answer correctly to climb up. Wrong answers push you down. Reach the top before time’s up! ⏱️|Responda corretamente para subir. Respostas erradas fazem você descer. Chegue ao topo antes que o tempo acabe!
Choose correct answers to score points!|Escolha a resposta correta para marcar pontos!
Which animal is known as the King of the Jungle?|Qual animal é conhecido como o rei da selva?
Which planet is known as the Red Planet?|Qual planeta é conhecido como o planeta vermelho?
How many days are there in a leap year?|Quantos dias há em um ano bissexto?
Which shape has 3 sides?|Qual figura tem três lados?
What do plants need to make food?|Do que as plantas precisam para produzir alimento?
Which of these is a mammal?|Qual destes animais é um mamífero?
Which number is even?|Qual número é par?
Which is the largest ocean on Earth?|Qual é o maior oceano da Terra?
Which gas do we breathe in to stay alive?|Qual gás respiramos para permanecer vivos?
How many minutes are there in one hour?|Quantos minutos há em uma hora?
How many legs does a spider have?|Quantas pernas tem uma aranha?
What color is the sky on a clear day?|Qual é a cor do céu em um dia sem nuvens?
Which fruit is yellow and curved?|Qual fruta é amarela e curva?
Which animal says 'meow'?|Qual animal faz miau?
What do bees make?|O que as abelhas produzem?
Which day comes after Monday?|Qual dia vem depois da segunda-feira?
What do we use to write on a blackboard?|O que usamos para escrever em um quadro-negro?
How many wheels does a bicycle have?|Quantas rodas tem uma bicicleta?
Which season is usually the coldest?|Qual costuma ser a estação mais fria?
What do we wear on our feet?|O que usamos nos pés?
Which shape is a ball most like?|Qual forma se parece mais com uma bola?
What is H2O commonly called?|Como chamamos H2O no dia a dia?
What do cows drink?|O que as vacas bebem?
Which animal can fly?|Qual animal pode voar?
How many days are there in a week?|Quantos dias há em uma semana?
What color are most leaves?|Qual é a cor da maioria das folhas?
Which transport moves on tracks?|Qual meio de transporte anda sobre trilhos?
Where do fish live?|Onde vivem os peixes?
Which is a farm animal?|Qual é um animal de fazenda?
What do we wear when it rains?|O que usamos quando chove?
What is the boiling point of water at sea level?|A que temperatura a água ferve ao nível do mar?
Which organ in the human body pumps blood?|Qual órgão bombeia o sangue no corpo humano?
How many continents are there on Earth?|Quantos continentes há na Terra?
Who wrote the famous play 'Romeo and Juliet'?|Quem escreveu a peça Romeu e Julieta?
What is the largest planet in our Solar System?|Qual é o maior planeta do Sistema Solar?
Which process do plants use to make their own food?|Qual processo as plantas usam para produzir seu alimento?
Which blood group is known as the universal donor?|Qual tipo sanguíneo é conhecido como doador universal?
O negative|O negativo
Which metal is used most for making wires?|Qual metal é mais usado na fabricação de fios?
In which direction does the Sun rise?|Em qual direção o Sol nasce?
Which language has the most native speakers in the world?|Qual idioma tem mais falantes nativos no mundo?
Mandarin Chinese|Chinês mandarim
What is the capital city of India?|Qual é a capital da Índia?
Which vitamin is produced when skin is exposed to sunlight?|Qual vitamina é produzida pela pele exposta à luz solar?
Vitamin A|Vitamina A
Vitamin B12|Vitamina B12
Vitamin C|Vitamina C
Vitamin D|Vitamina D
What is 9 × 7?|Quanto é 9 × 7?
Which gas do plants release during photosynthesis?|Qual gás as plantas liberam durante a fotossíntese?
Which planet is closest to the Sun?|Qual planeta está mais próximo do Sol?
What is the largest mammal on Earth?|Qual é o maior mamífero da Terra?
Blue whale|Baleia-azul
How many bones are there in an adult human body?|Quantos ossos há no corpo de um ser humano adulto?
What is the freezing point of water?|Qual é a temperatura de congelamento da água?
Which continent is also a country?|Qual continente também é um país?
Which instrument has black and white keys?|Qual instrumento tem teclas pretas e brancas?
Who is known as the Father of Computers?|Quem é conhecido como o pai da computação?
Which organ helps us breathe?|Qual órgão nos ajuda a respirar?
Which one is a renewable source of energy?|Qual destas é uma fonte de energia renovável?
Natural gas|Gás natural
How many sides does a hexagon have?|Quantos lados tem um hexágono?
The Great Wall is in which country?|Em qual país fica a Grande Muralha?
What is the main language spoken in Spain?|Qual é o principal idioma falado na Espanha?
Which force pulls objects toward Earth?|Qual força atrai os objetos em direção à Terra?
Which blood cells help in clotting?|Quais células do sangue ajudam na coagulação?
Red blood cells|Glóbulos vermelhos
White blood cells|Glóbulos brancos
What is the main gas found in the air we breathe?|Qual é o principal gás do ar que respiramos?
Which part of the plant is usually underground?|Qual parte da planta geralmente fica debaixo da terra?
What is the chemical symbol for table salt?|Qual é a fórmula química do sal de cozinha?
Who proposed the three laws of motion?|Quem propôs as três leis do movimento?
Which part of the cell contains genetic material?|Qual parte da célula contém o material genético?
Cell membrane|Membrana celular
What is the smallest prime number?|Qual é o menor número primo?
Which gas is most abundant in Earth's atmosphere?|Qual gás é mais abundante na atmosfera da Terra?
What is the powerhouse of the cell?|Qual organela é conhecida como a usina de energia da célula?
Golgi apparatus|Complexo de Golgi
What is the square root of 256?|Qual é a raiz quadrada de 256?
Who developed the theory of relativity?|Quem desenvolveu a teoria da relatividade?
Which element has the atomic number 1?|Qual elemento tem número atômico 1?
What is the value of Pi (π) rounded to two decimal places?|Qual é o valor de pi (π) arredondado para duas casas decimais?
What is the chemical formula for carbon dioxide?|Qual é a fórmula química do dióxido de carbono?
Who is known as the father of modern physics?|Quem é conhecido como o pai da física moderna?
What is the SI unit of electric current?|Qual é a unidade de corrente elétrica no Sistema Internacional?
What is 3/4 expressed as a percentage?|Quanto é 3/4 em porcentagem?
Which layer of the Earth is liquid?|Qual camada da Terra é líquida?
Inner core|Núcleo interno
Outer core|Núcleo externo
What is the process by which water changes from liquid to gas?|Como se chama a passagem da água do estado líquido para o gasoso?
Who formulated the law of universal gravitation?|Quem formulou a lei da gravitação universal?
Which part of the brain controls balance and coordination?|Qual parte do cérebro controla o equilíbrio e a coordenação?
What is the chemical symbol for gold?|Qual é o símbolo químico do ouro?
What is the value of 2³ × 3²?|Quanto é 2³ × 3²?
Which law explains why we need seat belts in cars?|Qual lei explica por que precisamos usar cinto de segurança?
Newton's first law|Primeira lei de Newton
Newton's second law|Segunda lei de Newton
Newton's third law|Terceira lei de Newton
Law of gravitation|Lei da gravitação
What is the pH of pure water at 25°C?|Qual é o pH da água pura a 25 °C?
Which scientist discovered penicillin?|Qual cientista descobriu a penicilina?
Which planet has the most moons in our Solar System?|Qual planeta tem mais luas no Sistema Solar?
What is the speed of light in vacuum (approximately)?|Qual é a velocidade aproximada da luz no vácuo?
What is the term for animals that eat both plants and meat?|Como se chamam os animais que comem plantas e carne?
In which part of the cell does photosynthesis mainly occur?|Em qual parte da célula ocorre a maior parte da fotossíntese?
What is the derivative of x²?|Qual é a derivada de x²?
Which gas causes the greenhouse effect the most among these?|Qual destes gases mais contribui para o efeito estufa?
What is the hardest natural substance on Earth?|Qual é a substância natural mais dura da Terra?
Pick the correct option for each.\n|Escolha a alternativa correta para cada pergunta.\n
Guess the hidden word in six tries. Each guess must be a real word. Letters turn green when correct and in the right spot, yellow when in the word but wrong spot, and gray when not in the word.|Descubra a palavra em seis tentativas. Verde indica uma letra na posição correta; amarelo indica uma letra na posição errada; cinza indica que ela não está na palavra.
You solved it!|Você descobriu!
Better luck next time!|Tente novamente na próxima partida!
Connect letters to form valid words. Fill the crossword grid to win. Drag across letters in sequence; release to submit.|Ligue as letras em sequência para formar palavras e completar o tabuleiro. Solte para confirmar.
Puzzle Solved!|Quebra-cabeça resolvido!
PUZZLE COMPLETE!|DESAFIO CONCLUÍDO!
TIME UP!|O TEMPO ACABOU!
ALREADY FOUND|JÁ ENCONTRADA
Hint: |Dica: 
Famous for keeping appointments away from doctors.|Fruta conhecida pelo ditado sobre manter o médico longe.
The engine that never burns fuel.|Um motor que nunca queima combustível.
When order forgets its manners.|Quando a ordem perde as boas maneiras.
A change, or a river’s patient handwriting.|Uma mudança ou a escrita paciente de um rio.
Seen when courage blinks.|Aparece quando a coragem hesita.
It blends without judgment.|Mistura tudo sem julgar.
Eats light, drinks quietly.|Consome luz e bebe em silêncio.
It obeys logic, not lunch breaks.|Obedece à lógica, sem pausa para almoço.
Striped thunder wrapped in fur.|Um trovão listrado e coberto de pelos.
It wears mountains down by being soft.|Desgasta montanhas com sua suavidade.
A traveler with no suitcase.|Um viajante sem mala.
Sunlight archived in jars.|Luz do sol guardada em potes.
Light taught to keep a straight face.|Luz que aprendeu a seguir em linha reta.
When sound is thinking.|Quando o som está pensando.
A road that moves while you stand still.|Uma estrada que se move enquanto você fica parado.
A curve that edits moods.|Uma curva que muda o humor.
Matter that refuses to wander.|Matéria que se recusa a vagar.
A path that stays to be chased.|Um caminho que fica para ser seguido.
Many acting as if one.|Muitos agindo como um só.
Color that remembers your eyes.|Uma cor que se lembra dos seus olhos.
It’s obvious only after you know it.|Só parece óbvio depois que você sabe.
🎯 HOW TO PLAY|COMO JOGAR
Tap and drag to pull the bow.|Toque e arraste para puxar o arco.
Release to shoot the arrow.|Solte para disparar a flecha.
Tap anywhere to start|Toque em qualquer lugar para começar
Arrows left|Flechas restantes
Tap anywhere to play again|Toque em qualquer lugar para jogar novamente
Tap to restart|Toque para reiniciar
Drag from the ball to aim; longer drag = more power, then release to shoot an arc toward the hoop. Sink shots through the net to score (ball respawns on the left platform); you have limited attempts, so wait for the ball to stop before aiming again. First to 5 points wins.|Arraste a partir da bola para mirar. Quanto maior a distância, maior a força. Solte para arremessar e espere a bola parar antes da próxima tentativa. Faça cinco pontos para vencer.
Classic Bowling Game.\nDrag, aim, and release to roll the ball.\nTwo rolls per frame, 10 frames total.|Mire, arraste e solte para lançar a bola.\nVocê tem dois lançamentos por rodada\ne dez rodadas por partida.
Classic Bowling Game.\nDrag, aim, and release to roll the ball.\nYou get 2 rolls per frame and a total of 10 frames.|Mire, arraste e solte para lançar a bola.\nVocê tem dois lançamentos por rodada\ne dez rodadas por partida.
New Game|Nova partida
Accelerate with Right ▶, brake with Left ◀. On mobile use the on-screen buttons. Approach stations slowly, press Action to open doors and dwell until completion. Stop at RED signals or you lose.|Acelere com Direita e freie com Esquerda. No celular, use os botões na tela. Chegue devagar às estações e pressione Ação para abrir as portas. Pare nos sinais vermelhos.
Line Complete!|Linha concluída!
Service Failed|Serviço encerrado
Sports Heads Football|Futebol de cabeças
⚽ SPORTS HEADS|FUTEBOL DE CABEÇAS
Move: ◀ ▶ or A / D\nJump: ↑ / W\nKick: Space / ⚽\n\nScore more goals in 60 seconds to win!|Mover: ◀ ▶ ou A / D\nSaltar: ↑ / W\nChutar: Espaço / Chutar\n\nMarque mais gols em 60 segundos para vencer!
Great match! Ready for the next one?|Boa partida! Vamos para a próxima?
Try again and beat the CPU!|Tente novamente e vença o computador!
Move: ◀ / ▶ or A / D • Jump: ↑ / ⬆ • Kick: Space / ⚽|Mover: ◀ / ▶ ou A / D • Saltar: ↑ • Chutar: Espaço / Chutar
Penalties: On your turn, choose Left/Center/Right and tap Action to shoot. On defense, choose a dive direction and tap Action to commit. Score more than the CPU in 5 rounds. Ties go to sudden death.|Na sua vez, escolha Esquerda, Centro ou Direita e toque em Ação para chutar. Na defesa, escolha um lado e toque em Ação para saltar. Marque mais gols em cinco rodadas. O empate leva à morte súbita.
Spot Kick Duel|Disputa de pênaltis
Your Shot: Choose Aim (◀ / ▶), Space to Kick|Seu chute: escolha a mira (◀ / ▶) e pressione Espaço para chutar
Defend: Choose Dive (◀ / ▶), Space to Dive|Defesa: escolha a direção (◀ / ▶) e pressione Espaço para saltar
Sudden Death! Your Shot.|Morte súbita! É a sua vez de chutar.
Saved by CPU!|O computador defendeu!
You Saved It!|Você defendeu!
Auto: Center Kick|Automático: chute no centro
Auto: Center Dive|Automático: defesa no centro
YOU WIN! 🏆|VOCÊ VENCEU!
Tap / Click / Space to Restart|Toque, clique ou pressione Espaço para reiniciar
YOU LOSE! 😞|VOCÊ PERDEU!
Tap / Click / Space to Retry|Toque, clique ou pressione Espaço para tentar novamente
Player 0 : 0 AI|Você 0 : 0 Computador
Nice hit!|Boa rebatida!
Player scores!|Ponto para você!
AI scores!|Ponto para o computador!
Right=Throttle, Left=Brake, Up/Down=Change Lane, Action=Doors/Horn|Direita: acelerar; Esquerda: frear; Cima/Baixo: trocar de faixa; Ação: portas/buzina
Doors OPEN|Portas ABERTAS
Doors CLOSED|Portas FECHADAS
Dwell cancelled (keep doors open & stopped)|Embarque cancelado: mantenha as portas abertas e o veículo parado
Terminal station — all passengers alighted|Estação final: todos os passageiros desembarcaram
Station served! Proceed to next.|Estação atendida! Siga para a próxima.
Signal passed at RED|Você ultrapassou o sinal VERMELHO
In station — Brake to stop (<= stop speed)|Na estação: freie até parar
In station — Open your doors (press Action)|Na estação: abra as portas pressionando Ação
Dwell cancelled — Open doors to board|Embarque cancelado: abra as portas
In station — Close your doors when boarding completes|Na estação: feche as portas quando o embarque terminar
Station served — Proceed to next station|Estação atendida: siga para a próxima
Maintain speed, obey signals, prepare for next station|Mantenha a velocidade, respeite os sinais e prepare-se para a próxima estação
SCORE: 0|PONTOS: 0
Drag from the ball → Aim & Release|Arraste a partir da bola → Mire e solte
Enemy destroyed|Inimigo destruído
Tap the left side of the screen\nto fly and dodge bullets from\nthe enemy and its minions.\nTo shoot, tap the enemy you\nwant to target.|Toque no lado esquerdo da tela\npara voar e desviar dos disparos.\nPara atirar, toque no inimigo\nque deseja acertar.
Avoid and hit:|Desvie e acerte:
Shoot to defend your player! Survive and score\nas high as you can.|Atire para defender seu personagem!\nSobreviva e marque o máximo de pontos.
Tap to Shoot|Toque para atirar
💥 Jet Destroyed!|Caça destruído!
🔁 Retry|Tentar novamente
Defeat enemies, dodge\nincoming bullets, and make\nit to the end of the level.|Derrote os inimigos, desvie\ndos disparos e chegue ao final\nda fase.
Tap or click to shoot when the oscillating aim line points at the enemy. Defeat three enemies and then a tougher mini-boss to clear Level 1.|Toque ou clique quando a mira apontar para o inimigo. Derrote três inimigos e o chefe para concluir a primeira fase.
Level 1 Cleared!|Fase 1 concluída!
Time: 30|Tempo: 30
Score 0|Pontos 0
Miss: 0/5|Erros: 0/5
Hold upper-left: Move Up\n|Segure no canto superior esquerdo: subir\n
Hold lower-left: Move Down\n|Segure no canto inferior esquerdo: descer\n
Tap right side: Fire Arrow\n|Toque no lado direito: disparar flecha\n
Shoot the falling bombs.\n|Acerte as bombas que caem.\n
Avoid enemy arrows!\n|Desvie das flechas inimigas!\n
You lose if you miss too many bombs or\nget hit.|Você perde se for atingido\nou deixar muitas bombas passarem.
Dodge bullets fired by the\nrobots and deactivate\nthem from behind.|Desvie dos disparos dos robôs\ne desative-os pelas costas.
Enemy deactivated!|Inimigo desativado!
Drag the joystick to aim (hold to charge) and release to shoot:|Arraste o controle para mirar, segure para carregar e solte para atirar:
Score |Pontos 
Your Score:   |Seus pontos:   
Landscape. Survive for 60s. Move with ←/→, jump with ↑ or Space. Shoot with Z or Action. Pick up crates for AK/Shotgun.|Sobreviva por 60 segundos. Mova-se com ←/→, salte com ↑ ou Espaço e atire com Z ou Ação. Recolha caixas para trocar de arma.
Temple Survived!|Você sobreviveu ao templo!
You Fell in the Temple!|Você caiu no templo!
Drag the scope to aim. When the aim turns red, tap to shoot:|Arraste a mira. Quando ela ficar vermelha, toque para disparar:
Avoid and Destroy:|Desvie e destrua:
Tap To Shoot|Toque para atirar
WINDOW SHOOTER|ATIRADOR NA JANELA
Shoot the terrorists, don't hit the hostages.|Atire nos inimigos e não acerte os reféns.
Missed: 0/5|Erros: 0/5
Move with arrow keys, collect all keys, and use / Action to dash through danger.Avoid demons and walls, then reach the glowing exit before the timer hits zero to win.|Mova-se com as setas, recolha todas as chaves e use Ação para avançar rapidamente. Evite os demônios e alcance a saída antes que o tempo acabe.
You escaped the Ghost Maze!|Você escapou do labirinto dos fantasmas!
Caught by a ghost...|Um fantasma pegou você...
Climb the collapsing tower! Move left/right and jump to survive. Avoid enemies and spikes. Collect gems for points!|Suba a torre que está desabando! Mova-se para os lados, salte, evite inimigos e espinhos e recolha gemas.
You Escaped the Tower!|Você escapou da torre!
Crushed in the Tower!|Você foi atingido na torre!
TRENCH DEFENCE|DEFESA DA TRINCHEIRA
Move with WASD/Arrows. Hold Space/Click/Action to shoot. Collect Vaccines for Burst (E or double-tap Action). Survive until the timer hits 0.|Mova-se com WASD ou setas. Segure Espaço, clique ou Ação para atirar. Recolha vacinas para usar a rajada com E ou dois toques em Ação. Sobreviva até o tempo acabar.
Infection Cleared!|Infecção eliminada!
Nano-bot Destroyed|Robô destruído
Tap anywhere to start!\nShoot the terrorists, don\'t hit the hostages.|Toque em qualquer lugar para começar!\nAtire nos inimigos e proteja os reféns.
You defeated all the terrorists!\n\nTap to play again|Você derrotou todos os inimigos!\n\nToque para jogar novamente
Vacc: 0|Vacinas: 0
Tower Blast|Defesa da torre
Time: ∞|Tempo: ∞
FLASH READY|PULSO PRONTO
TIME: |TEMPO: 
Kills: 0|Eliminações: 0
Aim: 0°|Mira: 0°
Power: 0%|Força: 0%
Shots: 1/10|Disparos: 1/10
Target: 6|Meta: 6
👾 Enemies: 1/4|Inimigos: 1/4
Car Runner|Corrida no trânsito
Swipe or use arrow keys to change lanes.\nAvoid traffic cars.\n\nCollect 100 coins to win.|Deslize ou use as setas para trocar de faixa.\nEvite os carros.\n\nRecolha as moedas indicadas na meta para vencer.
You escaped traffic!|Você escapou do trânsito!
Crashed into traffic!|Você bateu no trânsito!
Avoid obstacles like        ,      .\nSwipe up to jump, swipe twice for\nan extra bounce|Evite os obstáculos.\nToque ou clique para saltar.\nToque no ar para o salto duplo.\nTeclado: seta para cima ou espaço.
Tap LEFT/RIGHT to snap to each side of the rope. Tap ACTION to dash through tight gaps. Avoid obstacles, collect points, and survive until the timer ends.|Toque nos lados para mudar de posição na corda. Use Ação para atravessar espaços apertados. Evite obstáculos, recolha pontos e sobreviva até o tempo acabar.
You Reached the Sky Summit!|Você alcançou o topo!
Fell from the Rope!|Você caiu da corda!
Move to avoid shadows. Collect Light Shards to weaken or destroy shadows. Use Action to emit a pulse that pushes nearby shadows away. Survive until the timer hits 0 to win.|Desvie das sombras e recolha fragmentos de luz para enfraquecê-las. Use Ação para emitir um pulso e afastá-las. Sobreviva até o tempo acabar.
You Outlasted the Darkness!|Você venceu a escuridão!
Shadow Caught You|Uma sombra pegou você
Hold to charge power.\nRelease to shoot.|Segure para carregar a força.\nSolte para disparar.
Hold to charge power.\nRelease to shoot.\nCollect coins, avoid enemies.|Segure para carregar a força.\nSolte para disparar.\nRecolha moedas e evite inimigos.
Move through the haunted maze. Get close to a portal and press Action to rotate runes. Match all runes to seal the portal. Seal them all before time runs out. Avoid ghosts!|Atravesse o labirinto assombrado. Perto de um portal, use Ação para girar as runas. Combine todas para fechar o portal. Feche todos antes do tempo acabar e evite os fantasmas!
All portals sealed!|Todos os portais foram fechados!
You were caught!|Você foi pego!
Charges: 0|Cargas: 0
+3 FUEL|+3 COMBUSTÍVEL
Merge tiles with the same number by\nswiping in any direction.\nCombine numbers to reach 2048\nbefore the timer runs out!|Deslize em qualquer direção para juntar\npeças com o mesmo número.\nAlcance 2048 antes que o tempo acabe!
Tap letters on the wheel to form words. Submit to fill the crossword. Wrong guesses cost time and points—play smart! Shuffle to rearrange letters, Clear to reset your attempt.|Toque nas letras da roda para formar palavras e confirme para preencher o tabuleiro. Erros custam tempo e pontos. Use Misturar para reorganizar e Limpar para recomeçar.
Legendary! Puzzle Complete!|Excelente! Desafio concluído!
Tap the screen  to release the cargo from the moving crane. Stack  boxes to win. Don't miss more than 3!|Toque para soltar a carga do guindaste. Empilhe as caixas para vencer. Você pode errar até três vezes.
You're a Master Stacker!|Você domina as pilhas!
Stacking Failed!|A pilha caiu!
how to play|Como jogar
Time: --:--|Tempo: --:--
Tap a bottle, then tap another to pour. You can only pour onto the same color or into an empty bottle, and only the contiguous top segment moves. Make every non-empty bottle a single color.|Toque em um frasco e depois em outro para despejar. Você só pode despejar sobre a mesma cor ou em um frasco vazio. Deixe cada frasco com uma única cor.
Connect same|Conecte as iguais
LEVEL COMPLETED!|FASE CONCLUÍDA!
Swipe to cut ropes so the candy swings to collect stars and land in Om Nom's mouth.|Deslize para cortar as cordas. Faça o doce recolher estrelas e chegar à boca do personagem.
Sweet Success!|Sucesso açucarado!
Candy Lost!|O doce se perdeu!
AI's Turn|Vez do computador
AI THINKING...|COMPUTADOR JOGANDO...
Drag a shape from the tray and drop it on the board. Fill any full line to clear it and earn points.|Arraste as peças da bandeja para o tabuleiro. Complete uma linha para eliminá-la e ganhar pontos.
60 seconds|60 segundos
Score 100|100 pontos
Clear lines|Complete linhas
Start Game|Jogar
Target reached in time!|Meta alcançada a tempo!
Target not reached.|A meta não foi alcançada.
no moves|Sem jogadas
No moves|Sem jogadas
No moves! Tap Play Again|Sem jogadas! Toque em Jogar novamente
No moves left!|Não há mais jogadas!
Game Complete!|Jogo concluído!
Destroy all targets by deflecting lasers from the mirrors.|Gire os espelhos para refletir os lasers e destruir todos os alvos.
RESTART|REINICIAR
Connect matching colored nodes with non-overlapping paths that fill the entire grid. Drag from a node to draw a pipe through empty cells. Pipes cannot cross. Fill every cell to win.|Ligue os pontos da mesma cor sem cruzar os caminhos. Arraste a partir de um ponto e preencha todo o tabuleiro para vencer.
All flows connected!|Todas as conexões foram concluídas!
Time’s up!|O tempo acabou!
Flip over two tiles to find\n matching pairs.|Vire duas peças para encontrar\nos pares iguais.
Value: 100|Valor: 100
Bleach Memory Match|Memória de Bleach
Find and match the same\nnumbers on hidden tiles to\nclear the grid.|Encontre os números iguais\nnas peças escondidas para\nlimpar o tabuleiro.
Time: 01:00|Tempo: 01:00
Watch the sequence of highlighted\ntiles. Tap them back in the same order!|Observe a sequência de peças\niluminadas e repita na mesma ordem!
Tap a tile to increment it and its\nneighbors. Make all tiles the same\nto win!|Toque em uma peça para alterar seu valor\ne os dos vizinhos. Deixe todas iguais\npara vencer!
Solved in |Resolvido em 
 moves\n(Best: | jogadas\n(Recorde: 
Memorise the pairs shown in the guide below.\nMatch them within the given time to win!|Memorize os pares mostrados no guia.\nEncontre-os dentro do tempo para vencer!
Collect all the keys and reach the exit\nbefore time runs out.\nUse the on-screen buttons or arrow keys to move.|Recolha todas as chaves e alcance a saída\nantes que o tempo acabe.\nUse os botões na tela ou as setas para mover.
Keys: 0 / 0|Chaves: 0 / 0
Tap and hold to grow:|Toque e segure para aumentar:
Release to drop and land between the walls.|Solte para cair e aterrissar entre as paredes.
Tap and hold to grow|Toque e segure para aumentar
Release to drop|Solte para cair
Drag and drop each shape onto its matching outline before time runs out!|Arraste cada forma para o contorno correspondente antes que o tempo acabe!
Drag shapes to matching outlines!|Arraste as formas para os contornos iguais!
Play|Jogar
Circuit Complete!|Circuito completo!
Slide the tiles to arrange them\nin order. Tap a tile next to the\nempty space to move it.\nComplete the puzzle before\ntime runs out!|Deslize as peças para colocá-las\nem ordem. Toque em uma peça\nvizinha ao espaço vazio para mover.\nConclua antes que o tempo acabe!
Tap a tile to flip it and its neighbors.\nTurn all tiles white or black to win before\ntime runs out!|Toque em uma peça para inverter sua cor\ne a das vizinhas. Deixe todas brancas\nou pretas antes que o tempo acabe!
Well Done|Muito bem
The Royal Chef turned the treasury into soup! What do you do?|O cozinheiro real transformou o tesouro em sopa! O que você faz?
Chef Boris|Cozinheiro Boris
Eat the soup, money is overrated.|Comer a sopa. Dinheiro não é tudo.
Punish the chef! Demand your gold back.|Punir o cozinheiro e exigir o ouro de volta.
The sheep union demands stylish hats for all sheep.|O sindicato das ovelhas exige chapéus elegantes para todas.
Shepherdess Flo|Pastora Flo
Approve hats! Kingdom needs fashion.|Aprovar os chapéus! O reino precisa de moda.
No hats. Ban all sheep unions.|Negar e proibir os sindicatos de ovelhas.
A wizard duplicated all cows by accident.|Um mago duplicou todas as vacas por acidente.
Wizard Jeff|Mago Jeff
Host a milk festival!|Organizar um festival de leite!
Open a second castle just for cows.|Abrir um segundo castelo só para as vacas.
Moat is full of jelly. Locals start swimming competitions.|O fosso está cheio de gelatina. O povo começou a organizar corridas de natação.
Builder Pam|Construtora Pam
Sponsor jelly races!|Patrocinar as corridas de gelatina!
Replace jelly with water.|Trocar a gelatina por água.
A dragon ate all the royal shoes.|Um dragão comeu todos os sapatos reais.
Footman Rex|Criado Rex
Throw a barefoot festival.|Organizar um festival de pés descalços.
Bribe dragon with gold.|Subornar o dragão com ouro.
Your portrait painter added a moustache to all royal paintings.|O pintor colocou bigodes em todos os retratos reais.
Artist Luc|Artista Luc
Declare moustaches royal fashion.|Declarar o bigode como a nova moda real.
Paint over them all night.|Passar a noite corrigindo as pinturas.
Royal cats form a rock band. Noise is unbearable.|Os gatos reais formaram uma banda. O barulho está insuportável.
Maestro Kitty|Maestro Gatuno
Join the band as lead singer.|Entrar para a banda como vocalista.
Ban all cat concerts.|Proibir todos os shows dos gatos.
Royal Ego|Ego real
🎉 You Rule! 🎉\nSurvived 20 days of silliness.\n\nBards will sing your questionable wisdom.|Você governa!\nSobreviveu a 20 dias de confusão.\n\nOs bardos vão cantar sua sabedoria duvidosa.
👑 Your reign is over! 👑\nA stat maxed or mined out.\n\nNobody said ruling was easy!|Seu reinado acabou!\nUm dos recursos saiu do equilíbrio.\n\nNinguém disse que governar seria fácil!
Rule Again!|Governar novamente!
Guide Ruly through tricky royal decisions! Each choice you make affects your kingdom’s fate. Read the event, pick wisely, and balance the stats to survive. Make the wrong move... and chaos awaits!|Ajude o rei a tomar decisões! Leia cada evento e escolha com cuidado para manter os recursos do reino em equilíbrio e sobreviver.
🎉 You Rule!.Bards will sing your questionable wisdom.|Você governa! Os bardos vão cantar sua sabedoria duvidosa.
👑 Your reign is over!.Nobody said ruling was easy!|Seu reinado acabou! Ninguém disse que governar seria fácil!
Push the player with wind-bursts to reach the nest. Avoid spikes and rotors. Fans will push you in their direction. On mobile, use Left/Right and the Action (Up) button; on desktop use Arrow keys.|Use rajadas de vento para alcançar o ninho. Evite espinhos e hélices. Os ventiladores empurram você. No celular, use Esquerda, Direita e Ação. No computador, use as setas.
Breezed In!|Chegou com o vento!
Shredded by the Wind!|O vento pegou você!
Guide King David across dimensions and battle thieves and other obstacles.|Guie o rei David entre dimensões e enfrente os inimigos e obstáculos.
Guide King David across dimensions...|Guie o rei David entre dimensões...
LEVEL COMPLETE!|FASE CONCLUÍDA!
Tap left or right to jump\nbetween platforms and\ndodge enemies|Toque à esquerda ou à direita\npara saltar entre plataformas\ne desviar dos inimigos.
Tap left or right to jump\nbetween platforms and\ndodge enemies.|Toque à esquerda ou à direita\npara saltar entre plataformas\ne desviar dos inimigos.
Tap to start|Toque para começar
Distance:  |Distância:  
FLIP JUMP|SALTO INVERTIDO
Tap to flip:|Toque para inverter:
Distance: |Distância: 
Use ← → to move and [Jump] to leap. Stomp enemies, collect coins, and reach the flag before time runs out!|Use ← e → para mover e Saltar para pular. Pule sobre inimigos, recolha moedas e alcance a bandeira antes que o tempo acabe!
Reach the glowing exit at the top before the timer ends. Move left/right and jump across platforms. Avoid bouncing fireballs—they deal 1 damage. You have 3 hearts.|Alcance a saída iluminada no topo antes que o tempo termine. Mova-se para os lados e salte entre plataformas. Evite as bolas de fogo: você tem três vidas.
Dungeon Escape — You Reached the Exit!|Você alcançou a saída da masmorra!
Dungeon Escape — Try Again!|Tente escapar da masmorra novamente!
Level completed!|Fase concluída!
Try More|Tentar novamente
Oh, come on. Just press\non the button 4 time|Basta apertar\no botão quatro vezes.
Just press on it|Basta apertar o botão
Tap the Button|Toque no botão
Just go back It`s impossible\nto fail in this level!|Volte. É impossível\nfalhar nesta fase!
Try dying|Tente perder uma vida
Your corpse must\nfall on the button|Seu personagem precisa\ncair sobre o botão.
Hold an ingredient to pour into the glass. Release to stop. Swipe down on the glass to serve. Match each drink’s recipe ratios. Aim for perfect mixes for higher scores!|Segure um ingrediente para despejar no copo e solte para parar. Deslize para baixo sobre o copo para servir. Siga as proporções da receita para marcar mais pontos!
Service Master!|Mestre das bebidas!
Bar Closed!|Expediente encerrado!
Lassi (Buttermilk)|Bebida de iogurte
Lemon Soda|Soda de limão
Sweet Buttermilk|Bebida doce de leite
Level: |Nível: 
Drag tiles to make lines of 3 or more|Arraste as peças para formar linhas de três ou mais
Drag the correct ingredients from the table onto the plate in the right order before time runs out. Avoid mistakes!|Arraste os ingredientes para o prato na ordem correta antes que o tempo acabe. Evite erros!
Make: |Prepare: 
Delicious! Order Complete!|Delicioso! Pedido concluído!
Miss: 0|Erros: 0
Swipe the [basket] to collect [apple], [mango], and [orange].|Deslize a [basket] para recolher [apple], [mango] e [orange].
Do not collect [bomb].|Não recolha [bomb].
Score: 00|Pontos: 00
Time: 00:60|Tempo: 00:60
Life -1|Vida -1
AIM & DROP VEGETABLES\nMERGE MATCHING ONES\nDON’T FILL THE BOX\nMERGE TWO CABBAGES TO WIN|MIRE E SOLTE AS PEÇAS\nCOMBINE AS IGUAIS\nNÃO DEIXE A CAIXA ENCHER\nJUNTE DUAS PEÇAS FINAIS PARA VENCER
PLAY AGAIN|JOGAR NOVAMENTE
LEGENDARY MERGE|FUSÃO LENDÁRIA
BOX FULL|CAIXA CHEIA
SCORE|PONTOS
Fill: 0%|Ocupação: 0%
ICE ADDED|GELO ADICIONADO
ICE REMOVED|GELO REMOVIDO
Drag backwards from the striker to aim and set power. Release to shoot. Pocket white coins to score. The bot pockets black coins. Red queen gives +3 to whoever pockets it during their turn.|Arraste para trás a partir do disco para ajustar a mira e a força. Solte para disparar. Encaçape as peças brancas para pontuar. O computador usa as pretas. A rainha vermelha vale três pontos.
Carrom Champion!|Campeão do carrom!
Defeated! Try Again|Derrota! Tente novamente
Move with arrows. A = Attack, S = Special. Defeat your opponent!|Mova-se com as setas. A: atacar. S: ataque especial. Derrote seu oponente!
Victory! You are the Arena Champion!|Vitória! Você é o campeão da arena!
Defeat! Better luck next time.|Derrota! Tente novamente.
• You play White.\n• Tap a piece to see legal moves.\n• Tap a highlighted square to move.\n• Checkmate the CPU to win.|Você joga com as brancas.\nToque em uma peça para ver as jogadas válidas.\nToque em uma casa destacada para mover.\nDê xeque-mate no computador para vencer.
Checkmate — Black wins|Xeque-mate: as pretas venceram
Checkmate — White wins|Xeque-mate: as brancas venceram
Draw — Stalemate|Empate: sem jogadas válidas
Move mouse / finger to protect the balloon|Mova o dedo ou o mouse para proteger o balão
Tap / Click to play again|Toque ou clique para jogar novamente
Choose Rock, Paper, or Scissors before the countdown ends—beat the computer’s choice to win, or lose on a draw or timeout!|Escolha Pedra, Papel ou Tesoura antes da contagem terminar. Vença a escolha do computador. Empate ou tempo esgotado encerram a rodada!
Roll the dice to move.\nReach tile 100 to win!|Lance o dado para avançar.\nChegue à casa 100 para vencer!
Game Over! You didn’t reach tile 100.|Fim de jogo! Você não chegou à casa 100.
Classic Tic-Tac-Toe. Players take turns\nputting their marks in empty squares.\nThe first player to get 3 of\ntheir marks in a row\n(up, down, across, or diagonally)\nis the winner.|Os jogadores alternam suas marcas\nnas casas vazias. Quem alinhar\ntrês símbolos na horizontal, vertical\nou diagonal vence.
The match was a tie!|A partida terminou empatada!
Turn: Player (Bottom)|Vez de: Você (abaixo)
Player (Bottom)|Você (abaixo)
Bot (Top)|Computador (acima)
Time: 0:00|Tempo: 0:00
Tap to drop:               \n\nAligned on:\n\nStack up to win!|Toque para soltar:\n\nAlinhado em:\n\nEmpilhe para vencer!
Tap to drop the moving block.\nOnly the aligned part stays.\nStack up to win!|Toque para soltar o bloco.\nSó a parte alinhada permanece.\nEmpilhe para vencer!
Swipe left/right to toss the bomb to adjacent lanes. Make it explode near clusters of enemies. Don’t let it explode while you’re holding it! Collect power-ups for fuse, slow-mo, or a shield. Reach the target score before time runs out.|Deslize para os lados para lançar a bomba entre faixas. Exploda perto dos inimigos e não deixe a bomba estourar em suas mãos. Recolha bônus e alcance a meta antes que o tempo acabe.
Swipe to move the paddle and bounce the ball! Break bricks to score — each tile gives 10 points. Keep the ball in play and aim for a high score!|Deslize para mover a plataforma e rebater a bola! Cada bloco vale dez pontos. Mantenha a bola em jogo e marque o máximo de pontos!
Tap the crawling bugs to squash them. Letting too many escape ends the game. Survive until the timer hits 0 to win.|Toque nos insetos para esmagá-los. Se muitos escaparem, você perde. Sobreviva até o tempo acabar para vencer.
All Clear! You Survived!|Tudo limpo! Você sobreviveu!
Too Many Escaped!|Muitos insetos escaparam!
Best score|Recorde
Use the Joystick to control your horizontal movement and avoid obstacles.|Use o controle na tela para mover para os lados e evitar os obstáculos.
Alt: |Altura: 
Perfect Landing!|Pouso perfeito!
Hard Landing!|Pouso difícil!
Tap LEFT/RIGHT to switch lanes. Collect paint orbs to change your color. You can pass through barriers only when your color MATCHES theirs. Mismatch = instant game over!|Toque à ESQUERDA ou DIREITA para mudar de faixa. Recolha esferas para mudar de cor. Atravesse apenas as barreiras da SUA COR. Uma cor diferente encerra a partida!
Tap to play — dodge traffic and keep moving!|Toque para jogar, evite o trânsito e continue em movimento!
CURVY SNAKE|COBRA EM CURVAS
Tap / Click / press Space anywhere to toggle your turn direction.<br />Eat glowing orbs to grow and score. Don't crash into your own trail.|Toque, clique ou pressione Espaço para mudar a direção.<br />Recolha as esferas luminosas e evite colidir com seu próprio rastro.
Play again or go next|Jogue novamente ou continue
Defeat all d emons on each level. Tap action to attack; Tap to jump when grounded. Clear waves, enter the stairs to advance. Beat the final floor before the timer ends.|Derrote todos os demônios de cada andar. Use Ação para atacar e Saltar quando estiver no chão. Suba as escadas e conclua o último andar antes que o tempo acabe.
Slain: |Derrotados: 
Tower Purged!|Torre purificada!
The Night Consumes You|A noite venceu você
Time: 00:30|Tempo: 00:30
You Survived!|Você sobreviveu!
Survive for 30 seconds|Sobreviva por 30 segundos
Time: 00:|Tempo: 00:
Time Left: 02:00|Tempo restante: 02:00
Swipe to move and dodge the falling\nobjects. Reach the target score before\nthe timer runs out.|Deslize para mover e desviar dos objetos.\nAlcance a meta de pontos antes\nque o tempo acabe.
TRY AGAIN!|TENTE NOVAMENTE!
DREAM WEAVER — BRIDGES|TECELÃO DOS SONHOS: PONTES
Stand still ≈1s to conjure a bridge\ntoward the nearest platform.\nOverstay: spikes then crumble. Move to pause.|Fique parado por um segundo para criar\numa ponte até a plataforma mais próxima.\nNão demore: ela pode desabar!
Tap / Click to Start|Toque ou clique para começar
You Fell Asleep…|Você adormeceu...
You Wove the Dream!|Você teceu o sonho!
On a grid covered with,\n|Em um tabuleiro com\n
various objects, try to form\n|diversos objetos, forme\n
horizontal or vertical\n|linhas horizontais ou verticais\n
chains of at least three\n|com pelo menos três\n
identical ones by swapping\n|peças iguais, trocando\n
neighbouring objects. Find\n|peças vizinhas. Encontre\n
parts and food before the\n|as peças e a comida antes\n
timer runs out.|que o tempo acabe.
Parts to Collect:|Peças a recolher:
▶ Play Game|Jogar
Parts Collected:|Peças recolhidas:
⟳ Replay Level|Repetir fase
▶ Next|Continuar
⟳ Replay|Jogar novamente
Money: 0|Dinheiro: 0
Tap to Control:|Toque para controlar:
Tap a platform to jump forward.\nEach step has one safe and one fake glass tile — only one will hold your weight! Choose wisely and reach the top before time runs out. One wrong step, and it's game over! 💥|Toque em uma plataforma para saltar.\nEm cada passo, apenas um vidro é seguro!\nEscolha com cuidado e chegue ao topo\nantes que o tempo acabe.
SURVIVE 60 SECONDS.\n\n• Hold Left/Right buttons to move\n• Tap Punch to attack\n\nDestroy buildings and enemy units to score points. Avoid projectiles; your health is limited. If health drops to zero, it's game over.|SOBREVIVA POR 60 SEGUNDOS.\n\nSegure Esquerda/Direita para mover.\nToque em Atacar para golpear.\n\nDestrua construções e inimigos para pontuar. Evite os projéteis e proteja sua vida.
Faded Away|A luz se apagou
Use arrow keys or on-screen left/right to steer through the maze. Collect all dots to clear the level. Power pellets let you eat frightened ghosts for extra points.|Use as setas ou os controles na tela para atravessar o labirinto. Recolha todos os pontos. As pastilhas especiais permitem enfrentar os fantasmas por um tempo.
Stage Clear!|Fase concluída!
 Win by defeating enough enemies before time runs out.| Vença derrotando a quantidade indicada de inimigos antes que o tempo acabe.
Dist: 0|Distância: 0
⚠️ CHANGING SOON!|O SINAL VAI MUDAR!
⏰ Time's up!|O tempo acabou!
RED LIGHT|SINAL VERMELHO
🚫 Caught moving on red!|Você se moveu no vermelho!
Hold screen to move:|Segure a tela para mover:
Stop on red light.|Pare no sinal vermelho.
Move on green light.|Avance no sinal verde.
Distance Covered|Distância percorrida
Play Again!|Jogar novamente!
Tap or swipe to move, cross the road,\nand finish the level.|Use as quatro setas para se mover,\natravesse a rua e conclua a fase.
Move left/right. Only collect the highlighted target shape. Wrong shapes cost a life. Reach the target score before time runs out.|Mova-se para os lados e recolha apenas a forma indicada. Formas erradas custam uma vida. Alcance a meta antes que o tempo acabe.
Dodge the fireballs and help Player reach the key to unlock the gate|Desvie das bolas de fogo e alcance a chave para abrir o portão.
Swipe to guide your player\n|Deslize para guiar o personagem\n
through obstacles and\n|entre os obstáculos e\n
collect spaceship parts.\n|recolher peças da nave.\n
 Collect:| Recolha:
You missed too many parts!|Você deixou muitas peças passarem!
Tap and hold to stretch a stick that will be used to walk between platforms.|Toque e segure para esticar um palito e formar uma ponte entre as plataformas.
Tap to toss sticks at the ring.\nDon't hit another stick!|Toque para lançar palitos no círculo.\nNão acerte outro palito!
Tap to shoot:|Toque para atirar:
Avoid hitting:|Evite acertar:
SWIPE ASSASSIN|ATAQUE SILENCIOSO
Swipe to move\nKill enemies ONLY from behind\nFacing enemy = instant death|Deslize para mover\nAtaque apenas pelas costas\nSer visto pelo inimigo encerra a partida
MISSION CLEAR|MISSÃO CONCLUÍDA
All enemies eliminated|Todos os inimigos foram eliminados
You were spotted|Você foi descoberto
Tap the targets to score and reach\nthe goal within the given time.|Toque nos alvos para marcar pontos\ne alcançar a meta dentro do tempo.
Missed: 0|Erros: 0
Crashed! Try Again|Você bateu! Tente novamente
Hold to rise • Release to fall • Stay in the passage!|Segure para subir • Solte para descer • Fique na passagem!
Hold to fly:|Segure para voar:
Collect: —|Recolha: —
SPEED UP!|MAIS VELOCIDADE!
NEW GHOST!|NOVO FANTASMA!
Next Wave ▶|Próxima onda ▶
cycle color|Mudar de cor
Bomb Toss|Lançamento de bombas
Swipe left/right to toss the bomb to adjacent lanes. Make it explode near enemy clusters. Do not let it explode in your hands!|Deslize para os lados para lançar a bomba entre faixas. Exploda perto dos grupos de inimigos e não deixe a bomba estourar em suas mãos!
Use joystick to move.\nCollect junk to score and recharge battery.\nAvoid asteroids and satellites.\nBattery drains while moving.|Use o controle para mover.\nRecolha destroços para pontuar e recarregar.\nEvite asteroides e satélites.\nA bateria diminui enquanto você se move.
Battery: 100%|Bateria: 100%
Shield: 100%|Escudo: 100%
Mission Complete!|Missão concluída!
Battery Depleted!|A bateria acabou!
MISSION COMPLETE|MISSÃO CONCLUÍDA
START MISSION|INICIAR MISSÃO
NEXT SECTOR|PRÓXIMO SETOR
MISSION BRIEFING|INSTRUÇÕES DA MISSÃO
Destroy meteors to gain energy.|Destrua meteoros para ganhar energia.
Reach the target energy before shields are lost.|Alcance a meta de energia antes que o escudo acabe.
Tap meteors to shoot lasers.|Toque nos meteoros para disparar lasers.
Tap collectables to gain bonuses (optional).|Toque nos itens para ganhar bônus.
Score: 00/100|Pontos: 00/100
Navigate the alien world and take pictures of plants from a distance. Protect yourself from animals by teleporting. Tap the teleport button, then select a spot inside the dotted circle to move.|Explore o planeta e fotografe as plantas à distância. Evite os animais usando o teletransporte. Toque no botão e depois em um lugar dentro do círculo pontilhado para se mover.
Shoot bullet!|Disparar!
Shoot, block attacks, dodge\nrockets, and take down the\nrobots to clear the level.|Atire, bloqueie os ataques, desvie\ndos foguetes e destrua os robôs\npara concluir a fase.
Stack Tower 3D – Neon|Torre de blocos 3D
Neon perfection!|Alinhamento perfeito!
Try again|Tentar novamente
"""

WORDS = """Lion=Leão|Tiger=Tigre|Elephant=Elefante|Monkey=Macaco|Mars=Marte|Earth=Terra|Venus=Vênus|Jupiter=Júpiter|Mercury=Mercúrio|Saturn=Saturno|Neptune=Netuno|Triangle=Triângulo|Square=Quadrado|Circle=Círculo|Rectangle=Retângulo|Sunlight=Luz solar|Water=Água|Oxygen=Oxigênio|Nitrogen=Nitrogênio|Hydrogen=Hidrogênio|Helium=Hélio|Dolphin=Golfinho|Shark=Tubarão|Crocodile=Crocodilo|Frog=Sapo|Pacific=Pacífico|Atlantic=Atlântico|Indian=Índico|Arctic=Ártico|Blue=Azul|Red=Vermelho|Green=Verde|Yellow=Amarelo|Banana=Banana|Apple=Maçã|Orange=Laranja|Grapes=Uvas|Cat=Gato|Dog=Cachorro|Cow=Vaca|Bird=Pássaro|Honey=Mel|Milk=Leite|Sugar=Açúcar|Salt=Sal|Tuesday=Terça-feira|Wednesday=Quarta-feira|Sunday=Domingo|Friday=Sexta-feira|Chalk=Giz|Pencil=Lápis|Pen=Caneta|Brush=Pincel|Winter=Inverno|Summer=Verão|Spring=Primavera|Autumn=Outono|Shoes=Sapatos|Gloves=Luvas|Hat=Chapéu|Scarf=Cachecol|Sphere=Esfera|Cube=Cubo|Cone=Cone|Cylinder=Cilindro|Juice=Suco|Tea=Chá|Coffee=Café|Eagle=Águia|Penguin=Pinguim|Ostrich=Avestruz|Train=Trem|Bus=Ônibus|Car=Carro|Plane=Avião|Sea=Mar|Ocean=Oceano|Desert=Deserto|Forest=Floresta|Goat=Cabra|Wolf=Lobo|Raincoat=Capa de chuva|Heart=Coração|Lungs=Pulmões|Brain=Cérebro|Stomach=Estômago|Photosynthesis=Fotossíntese|Respiration=Respiração|Digestion=Digestão|Evaporation=Evaporação|Copper=Cobre|Iron=Ferro|Gold=Ouro|Silver=Prata|East=Leste|West=Oeste|North=Norte|South=Sul|English=Inglês|Spanish=Espanhol|Hindi=Hindi|Delhi=Délhi|Tokyo=Tóquio|Paris=Paris|London=Londres|Piano=Piano|Guitar=Violão|Violin=Violino|Flute=Flauta|Solar=Solar|Coal=Carvão|Petroleum=Petróleo|China=China|Japan=Japão|Russia=Rússia|Brazil=Brasil|Gravity=Gravidade|Friction=Atrito|Magnetism=Magnetismo|Platelets=Plaquetas|Plasma=Plasma|Root=Raiz|Stem=Caule|Leaf=Folha|Flower=Flor|Nucleus=Núcleo|Cytoplasm=Citoplasma|Mitochondria=Mitocôndria|Ribosome=Ribossomo|Ribosomes=Ribossomos|Cerebellum=Cerebelo|Cerebrum=Cérebro|Medulla=Bulbo|Omnivores=Onívoros|Herbivores=Herbívoros|Carnivores=Carnívoros|Chloroplast=Cloroplasto|Chloroplasts=Cloroplastos|Diamond=Diamante|Quartz=Quartzo|Talc=Talco|Granite=Granito|Australia=Austrália|Europe=Europa|Africa=África|Asia=Ásia|Ammeter=Amperímetro|Ampere=Ampere|Volt=Volt|Watt=Watt|Ohm=Ohm|Crust=Crosta|Mantle=Manto|Sublimation=Sublimação|Condensation=Condensação|Freezing=Congelamento|Melting=Fusão|Meteor=Meteoro|Rock=Pedra|Paper=Papel|Scissors=Tesoura|Lemon=Limão|Yogurt=Iogurte|Soda=Soda|Ice=Gelo|Mint=Hortelã|Play=Jogar|Start=Jogar|Restart=Reiniciar|Replay=Jogar novamente|Next=Continuar|Resume=Continuar|Pause=Pausar|Jump=Saltar|Attack=Atacar|Action=Ação|Shoot=Atirar|Punch=Atacar|Hint=Dica|Shuffle=Misturar|Clear=Limpar|Submit=Confirmar|Enter=Confirmar|Easy=Fácil|Medium=Médio|Hard=Difícil|Loading=Carregando|Loading...=Carregando...|Victory=Vitória|Defeat=Derrota|Draw=Empate|You=Você|Player=Você|Computer=Computador|Correct=Correto|Wrong=Incorreto|Success=Sucesso|Settings=Configurações|Sound=Som|Music=Música|Volume=Volume|On=Ativado|Off=Desativado|Goal=Gol|Goals=Gols|Round=Rodada|Rounds=Rodadas|Left=Esquerda|Right=Direita|Center=Centro|Up=Cima|Down=Baixo|White=Brancas|Black=Pretas|Health=Vida|Enemies=Inimigos|Battery=Bateria|Shield=Escudo|Stage=Fase|Win=Vitória|Lose=Derrota"""


def main():
    path = ROOT / 'data/localization-pt.json'
    dictionary = json.loads(path.read_text(encoding='utf-8'))
    for line in REVIEWED.strip().splitlines():
        english, translated = line.split('|', 1)
        english = english.replace('\\n', '\n')
        dictionary[english] = translated.replace('\\n', '\n')
    for item in WORDS.split('|'):
        english, translated = item.split('=', 1)
        dictionary[english] = translated
    dictionary.update({
        'Zebra':'Zebra', 'Moonlight':'Luz da lua', 'Wind':'Vento', 'Snow':'Neve',
        'Horse':'Cavalo', 'Bread':'Pão', 'Spoon':'Colher', 'Fork':'Garfo', 'Oil':'Óleo',
        'Boat':'Barco', 'Sky':'Céu', 'Sunglasses':'Óculos de sol', 'Helmet':'Capacete',
        'Giraffe':'Girafa', 'Hippopotamus':'Hipopótamo', 'Liver':'Fígado', 'Kidney':'Rim',
        'India':'Índia', 'French':'Francês', 'German':'Alemão', 'Electricity':'Eletricidade',
        'Argon':'Argônio', 'Carbon':'Carbono', 'Hypothalamus':'Hipotálamo',
        'Detritivores':'Detritívoros', 'Graphite':'Grafite', 'Row':'Tentativa',
        'WORDLY':'PALAVRA DO DIA', 'ENTER':'ENVIAR', 'DEL':'APAGAR',
        'Easy':'Fácil', 'Medium':'Médio', 'Hard':'Difícil', 'Bomb':'Bomba',
        'Stop':'Parar', 'GO':'VÁ', 'READY':'PRONTO', 'GOAL':'GOL', 'PAUSE':'PAUSAR',
        'LEFT':'ESQUERDA', 'RIGHT':'DIREITA', 'ACTION':'AÇÃO', 'ATTACK':'ATACAR',
        'JUMP':'SALTAR', 'FIRE':'ATIRAR', 'SHOOT':'ATIRAR', 'PUNCH':'ATACAR',
        'Clear Cell':'Limpar casa', 'New Puzzle':'Novo desafio', 'Check':'Verificar',
        'Pencil Mode':'Modo de anotações', 'Notes':'Anotações', 'Erase':'Apagar',
        'Flip Board':'Inverter tabuleiro',
        'Stand still ≈1s → bridge grows toward next platform • Overstay → spikes → crumble':'Fique parado por 1 s para criar uma ponte até a próxima plataforma. Não demore: ela pode desabar.',
        'Back':'Voltar', 'Bullseyes':'Acertos no centro', 'Champions!':'Campeões!',
        'Clue':'Dica', 'Clue:':'Dica:', 'Cores':'Núcleos', 'Cumin':'Cominho',
        'Defeated!':'Derrota!', 'Draw!':'Empate!', 'END':'FIM', 'Kaboom!':'Explosão!',
        'LADDER!':'ESCADA!', 'Order Failed! Try Again':'Pedido não concluído! Tente novamente',
        'Paused':'Pausado', 'Paused\nResume':'Pausado\nContinuar', 'Pop:':'Estoure:',
        'Reach <b>{{target}}</b> points to win.<br />Avoid your own tail. The world wraps around.':'Alcance <b>{{target}}</b> pontos para vencer.<br />Evite seu próprio rastro. Ao sair de uma borda, você reaparece na outra.',
        'SNAKE!':'COBRA!', 'SURVIVE!':'SOBREVIVA!', 'Shields':'Escudos', 'Slice:':'Corte:',
        'Stacked:':'Empilhadas:', 'Stars':'Estrelas',
        'You hit {bullseyes} bullseyes in {arrows} arrows!':'Você acertou o centro {bullseyes} vezes com {arrows} flechas!',
        'You only hit {bullseyes} bullseyes in {arrows} arrows.':'Você acertou o centro {bullseyes} vezes com {arrows} flechas.',
        'Tap to stop the moving block at the right time and stack it perfectly. Each perfect stop builds your combo. Get {perfectCount} perfect stacks in 60 seconds to win!':'Toque para parar o bloco no momento certo e empilhar. Cada alinhamento perfeito aumenta a sequência. Faça {perfectCount} alinhamentos perfeitos em 60 segundos para vencer!',
        'Drag a shape from the tray and drop it on the board. Fill any full line (any colors) to clear it and earn bonus points.':'Arraste uma peça da bandeja para o tabuleiro. Complete uma linha, com qualquer cor, para eliminá-la e ganhar pontos extras.',
        'Draw lines to block enemies':'Desenhe linhas para bloquear os inimigos',
        'Protect the core':'Proteja o núcleo', 'Tap to drop the block':'Toque para soltar o bloco',
        'Perfect alignment gives glow':'Um alinhamento perfeito faz a torre brilhar',
        'Reach 20 to win':'Empilhe 20 blocos para vencer', 'Roll Dice':'Lançar dado',
        'Result':'Resultado', 'Game':'Jogo', 'YOU WIN':'VOCÊ VENCEU',
        'Swipe left/right to move, swipe down or tap ▼ to fall faster, tap ⟳ to rotate, tap ⏬ to drop.':'Deslize para os lados para mover. Deslize para baixo ou toque em ▼ para acelerar, em ⟳ para girar e em ⇓ para soltar.',
        'Tip: Use ◀ / ▶ to choose Aim/Dive, Space to Kick/Dive. Mobile buttons included.':'Dica: use ◀ e ▶ para escolher a direção e Espaço para chutar ou defender. No celular, use os botões na tela.',
        "Tap on the screen to curve and create your snake's path.":'Toque na tela para mudar a direção e criar o caminho da cobra.',
        'Avoid hitting your own trail as the world wraps around the edges.':'Evite colidir com seu próprio rastro. Ao sair por uma borda, você reaparece na outra.',
        'Eat:':'Coma:', 'Food':'Comida', 'to score points and grow.':'para marcar pontos e crescer.',
        'You will be asked ${maxQ} ${difficultyLabel} questions.\n':'Você responderá ${maxQ} perguntas.\n',
        'Get at least ${required} correct answers before the time runs out to win!':'Acerte pelo menos ${required} respostas antes que o tempo acabe para vencer!',
        'Connect same-colored dots\nby dragging to make chains.\n\nReach ${this.targetScore} points\nwithin ${this.timeLimit} seconds!':'Arraste para conectar os pontos\nda mesma cor.\n\nAlcance ${this.targetScore} pontos\nem ${this.timeLimit} segundos!',
        'Swipe to control the snake.\nEat food to grow longer and\nscore points. Hitting a wall or\nbiting yourself ends the game.\n Target:${this.targetScore}':'Deslize para guiar a cobra.\nComa para crescer e marcar pontos.\nEvite as paredes e seu próprio corpo.\nMeta: ${this.targetScore}',
        'Use the joystick to dodge enemies.\nSurvive for ${this.timer} seconds to win.':'Use o controle para desviar dos inimigos.\nSobreviva por ${this.timer} segundos para vencer.',
        'Win at ${this.targetScore} hits.\nGame over after ${this.missLimit} misses.':'Alcance ${this.targetScore} pontos.\nA partida termina após ${this.missLimit} erros.',
        'Collect ${totalParts} parts to repair your ship.\n':'Recolha ${totalParts} peças para reparar sua nave.\n',
        'You can miss up to ${maxMisses} parts.\n':'Você pode deixar até ${maxMisses} peças passarem.\n',
        'You have ${maxHealth} health.':'Você tem ${maxHealth} pontos de vida.',
        'Next Power-Up in: ${nextTarget - this.score}':'Próximo bônus em: ${nextTarget - this.score}',
        'Score ${score} reached in time!':'${score} pontos alcançados a tempo!',
        'Terrorists killed: ${this.kills}\n\nTap to restart':'Inimigos eliminados: ${this.kills}\n\nToque para reiniciar',
        'You collected all junk!\nScore: ${this.score}':'Você recolheu todos os destroços!\nPontos: ${this.score}',
        'Slice (${sliceList.join(", ")}) images. Avoid ${bombName}.':'Corte os itens (${sliceList.join(", ")}). Evite ${bombName}.',
        'Slice the objects to score. Avoid ${bombName}.':'Corte os itens para pontuar. Evite ${bombName}.',
        'Checkmate — ${winner} wins':'Xeque-mate: vitória de ${winner}',
        '${stm} to move — ${who}':'Vez de ${stm} — ${who}',
        'Doors OPEN — Boarding… ${sec}s':'Portas ABERTAS — Embarque… ${sec}s',
        '+${boarded} passengers':'+${boarded} passageiros',
        '-${off} passengers':'-${off} passageiros',
        'Sudden Death (R${this.round})':'Morte súbita (rodada ${this.round})',
        'Solve: ${questionStr}':'Resolva: ${questionStr}',
        'FINAL SCORE\n${this.score}':'PONTUAÇÃO FINAL\n${this.score}',
        "Tap anywhere to start!\nShoot the terrorists, don't hit the hostages.":'Toque em qualquer lugar para jogar!\nAcerte os inimigos e proteja os reféns.',
        'You defeated all the terrorists!\n\nTap to play again':'Você derrotou todos os inimigos!\n\nToque para jogar novamente',
        'Terrorists killed:':'Inimigos eliminados:',
        'Terrorists killed':'Inimigos eliminados',
        'GOAL!':'GOL!', 'Reshuffle':'Misturar novamente', 'Replay Level':'Repetir fase',
        'Stacked':'Empilhadas', 'Popularity':'Popularidade', 'EgoSelf':'Ego', 'Chaos':'Caos',
        'Pistol':'Pistola', 'Shotgun':'Escopeta', 'Rifle':'Rifle', 'Rocket Launcher':'Lança-foguetes',
    })
    dictionary['Tap left or right to switch positions.']='Cada toque troca o personagem de lado.\nA posição do toque não escolhe o lado.'
    path.write_text(json.dumps(dictionary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'web/game-localization.js').write_text('window.__BALTIGO_PT=' + json.dumps(dictionary, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/') + ';\n', encoding='utf-8')
    print(json.dumps({'phrases':len(dictionary)}))


if __name__ == '__main__':
    main()
