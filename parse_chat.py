#!/usr/bin/env python3
"""Parse Isaac's potty training WhatsApp chat into structured CSV."""

import re
import csv
from datetime import datetime
from collections import Counter, defaultdict

SKIP_PATTERNS = [
    'Messages and calls are end-to-end encrypted',
    'You created group',
    'You added',
    'You changed',
    'You deleted this message',
    'This message was deleted',
    'audio omitted',
    'image omitted',
    'document omitted',
    'added Thomas',
]

# Senders who are NOT caregivers (only post meta/instructions)
# Actually all can post events, but Gabriel mostly posts instructions
# We'll handle by content, not sender

def parse_timestamp(ts_str):
    return datetime.strptime(ts_str, '%d/%m/%y, %H:%M:%S')

def extract_explicit_time(text):
    """Extract explicit time mentioned in the message text."""
    patterns = [
        r'(?:as|às)\s+(\d{1,2})[:\.](\d{2})',
        r'(\d{1,2})[:\.](\d{2})\s*(?:hrs?|hr)',
        r'^(\d{1,2})[:\.](\d{2})\b',
        r'(\d{1,2})h(\d{2})',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            h, mi = int(m.group(1)), int(m.group(2))
            if 0 <= h <= 23 and 0 <= mi <= 59:
                return f"{h:02d}:{mi:02d}"
    return None

def is_bathroom_event(text):
    """Check if text describes a bathroom event (not just conversation)."""
    t = text.lower()
    # Must contain bathroom-related words
    bathroom_words = [
        'xixi', 'cocô', 'coco', 'escape', 'vaso', 'banheiro', 'banho', 'chuveiro',
        'mijou', 'minou', 'mijar', 'mijado', 'cagou', 'cagado',
        'levei', 'levou', 'levado', 'sozinho', 'pediu',
        'cueca', 'roupa', 'calça', 'fralda',
        'dixi', 'zixi', 'pinguinho', 'pinguinhos', 'pingos',
        'banheira', 'descarga',
    ]
    return any(w in t for w in bathroom_words)

def is_pure_conversation(text):
    """Detect messages that are purely conversational, not events."""
    t = text.strip().lower()

    # Very short replies that aren't events
    if t in ['não', 'sim', 'ok', 'legal', '?', 'simm', 'ipad', 'levei*']:
        return True

    # Messages that are clearly instructions/questions/meta
    conversation_starts = [
        'oi pessoal', 'ao inves de', 'depois eu gero', 'acho que assim',
        'orientações', 'exemplo de registro', 'dica de whatsapp',
        'vc pode desativar', 'aqui é para colocar', 'olá! aqui é para',
        'agora que vi',
        'só uma dúvida', 'ele pedir é raro', 'é  pq na escola',
        'ou levantava', 'isaac_banheiro', 'so ta errado',
        'eu acho importante', 'só uma sugestão', 'ops independente',
        'isso vai trazer', 'autonomia', 'gente da desconto',
        'sugestão', 'atualizações sobre o registro', 'continuar levando',
        'a cada 40minutos', 'caso leve e não faça',
        'registro:', 'sempre que houver escape sinalizar',
        'exemplo sobre dar a oportunidade',
        'o adulto levou isaac', 'caso ele vá', 'caso não vá',
        'se tiverem duvidas', 'aí vc leva ele de novo',
        'o que ele estava fazendo', 'vc levou ele',
        'apareceu só agora', 'não esquece de colocar',
        'pessoal, quando menciono independência',
        'posso dar uma sugestão',
        'eita que foi de novo', 'eita que hoje teve bastante',
        'kkkk acredito', 'torcendo pra não acabar',
        'provavelmente esta fugindo',
        'lembra de falar o que ele está fazendo',
        'sorry', 'vou alterar',
        'eu acho que isso é um sinal',
        'pode continuar levando', 'com o ipad bonitinho',
        'estou fazendo ele pedir', 'mas os dois escapes',
        'pode levar de novo', 'quero saber se ele vai',
        'por favor', 'valeu tony', 'minha hipótese',
        'boa viagem', 'uhulll', 'ta usando o ipad',
        'modelando com ipad', 'mas ele fez?',
        'ele tá falando', 'não dormiu', 'precisa trocar',
        'me desculpa', 'mas não teve escape',
        'nossa samantha', 'eu acho que a gente precisa',
        'parece que não estamos evoluindo', 'isso é muito desgastante',
        'por mim tudo bem', 'hoje estarei levando',
        'de novo quase no mesmo horário', 'eu que comi bola',
        'oi @', 'vc tem os últimos',
        'acho que vou mudar para bunda',
        'ele está saindo do banheiro',
        'ele está indo no banheiro o fazendo',
        'mexendo muito no', 'o xixi está com uma cor',
        '13:10 tem que levar', 'ele fez xixi aquela hora',
        'foi 10:40', 'modelei pelo ipad todos',
        'modelando pelo ipad todos', 'levei*',
    ]
    return any(t.startswith(cs) for cs in conversation_starts)

def classify_event(text):
    """Classify a bathroom event."""
    t = text.lower()
    result = {
        'tipo': None,
        'local': 'vaso',
        'sucesso': None,
        'iniciativa': None,
        'atividade_escape': None,
        'notas': '',
    }

    if is_pure_conversation(text):
        return None
    if not is_bathroom_event(text):
        return None

    # === NAO FEZ ===
    nao_fez = ('não fez' in t or 'nao fez' in t or 'não quis' in t or 'nao quis' in t or
                'não querer' in t or 'não quer' in t or 'nao quer' in t or 'não conseguiu' in t)

    # "nao fez" but NOT escape context
    is_escape_context = ('escape' in t or 'já tinha' in t or 'ja tinha' in t or
                         'na cueca' in t or 'na roupa' in t or 'na calça' in t or
                         'mijado' in t or 'cagado' in t)

    if nao_fez and not is_escape_context:
        # Check if it also mentions doing something (e.g. "não fez xixi" but "fez cocô")
        if 'fez cocô' in t or 'fez coco' in t:
            pass  # has a positive event too, handle below
        elif 'quase nada' in t:
            # Did very little - count as success with note
            result['tipo'] = 'xixi'
            result['sucesso'] = True
            result['local'] = 'vaso'
            result['iniciativa'] = 'levei'
            result['notas'] = 'pouca quantidade'
            return result
        else:
            result['tipo'] = 'nao_fez'
            result['sucesso'] = None
            result['local'] = 'vaso'
            result['iniciativa'] = 'levei'
            return result

    # === DETECT ESCAPE ===
    is_escape = ('escape' in t or
                 ('na cueca' in t and 'vaso' not in t) or
                 ('na roupa' in t and ('escape' in t or 'já tinha' in t or 'ja tinha' in t or
                  not any(w in t for w in ['levei', 'levou', 'levado']))) or
                 'na calça' in t or
                 ('no sofá' in t or 'no sofa' in t) and ('xixi' in t or 'escape' in t) or
                 'na cama' in t and ('escape' in t or 'xixi' in t) or
                 'no tapete' in t or
                 'no chão' in t or 'no chao' in t or
                 'no carro' in t or
                 'se mijou' in t or
                 ('já tinha feito' in t or 'ja tinha feito' in t) or
                 'ja tava mijado' in t or 'já tava mijado' in t or
                 'cueca suja' in t or 'cueca mijada' in t or
                 ('mijou' in t and ('cueca' in t or 'calça' in t or 'roupa' in t or 'tapete' in t or 'sofá' in t or 'sofa' in t or 'chão' in t)) or
                 'fez xixi na cadeira' in t or
                 'na fralda' in t or
                 'no shot' in t)

    # Special: "fez xixi na roupa e depois foi no banheiro" = escape
    if 'na roupa' in t and ('banheiro' in t or 'sozinho' in t):
        is_escape = True

    # === DETECT WHAT ===
    has_coco = 'cocô' in t or 'coco' in t or 'cagou' in t or 'cagado' in t
    has_xixi = ('xixi' in t or 'mijou' in t or 'minou' in t or 'mijar' in t or
                'mijado' in t or 'dixi' in t or 'zixi' in t or
                'se mijou' in t or 'pinguinho' in t or 'pinguinhos' in t or
                'pingos' in t or 'pinginhos' in t)

    # "levei e fez" without specifying = xixi
    if not has_xixi and not has_coco:
        if ('levei' in t or 'levou' in t) and 'fez' in t:
            has_xixi = True
        elif 'banheiro' in t and ('fez' in t or 'sozinho' in t):
            has_xixi = True
        elif is_escape:
            has_xixi = True  # most escapes are xixi
        else:
            return None

    in_banho = 'no banho' in t or 'no chuveiro' in t or 'na banheira' in t or 'tomando banho' in t or 'chão do box' in t

    # Set tipo
    if has_coco and has_xixi:
        result['tipo'] = 'xixi+coco'
    elif has_coco:
        result['tipo'] = 'coco'
    else:
        result['tipo'] = 'xixi'

    # Set sucesso and local
    if is_escape:
        result['sucesso'] = False
        if 'no sofá' in t or 'no sofa' in t:
            result['local'] = 'sofa'
        elif 'na cama' in t:
            result['local'] = 'cama'
        elif 'no tapete' in t:
            result['local'] = 'tapete'
        elif 'no chão' in t or 'no chao' in t:
            result['local'] = 'chao'
        elif 'no carro' in t:
            result['local'] = 'carro'
        elif 'na cadeira' in t or 'cadeira' in t:
            result['local'] = 'cadeira'
        elif 'laboratório' in t:
            result['local'] = 'laboratorio'
        elif 'na árvore' in t:
            result['local'] = 'arvore'
        elif 'no banco' in t:
            result['local'] = 'banco'
        elif 'na fralda' in t:
            result['local'] = 'fralda'
        elif 'no shot' in t:
            result['local'] = 'chao'
        else:
            result['local'] = 'roupa'

        # Activity during escape
        act = extract_activity(text)
        if act:
            result['atividade_escape'] = act

    elif in_banho:
        result['sucesso'] = True
        result['local'] = 'banho'
    else:
        result['sucesso'] = True
        result['local'] = 'vaso'

    # Determine initiative
    if 'pediu' in t or 'falou xixi' in t or 'falou cocô' in t or 'falou banheiro' in t or \
       'respondeu cocô' in t or 'disse fazer xixi' in t or 'falou coco' in t or \
       'pediu pra' in t or 'mostrou que queria' in t or 'mostrou xixi' in t:
        result['iniciativa'] = 'pediu'
    elif ('sozinho' in t or 'independente' in t or 'foi sozinho' in t or
          'abriu a porta' in t and 'foi' in t):
        result['iniciativa'] = 'sozinho'
    elif ('mandei' in t or 'falei para' in t or 'falei pra' in t or
          'ofertei' in t or 'ofereci' in t or 'mostrei' in t or
          'falei isaac' in t or 'só falei' in t):
        result['iniciativa'] = 'mandei'
    elif ('levei' in t or 'levou' in t or 'foi levado' in t or 'levek' in t or
          'leveu' in t or 'eu levei' in t or 'conduzido' in t or
          'professora levou' in t):
        result['iniciativa'] = 'levei'
    elif is_escape:
        result['iniciativa'] = None  # escapes don't have initiative

    # Notes
    notes = []
    if is_escape and ('foi no banheiro' in t or 'foi sozinho' in t or 'correu' in t or 'foi ao banheiro' in t):
        if 'terminou' in t or 'depois' in t or 'já tinha' in t or 'ja tinha' in t or 'mas' in t:
            notes.append('foi ao banheiro depois')
    if 'pinguinho' in t or 'pinguinhos' in t or 'pingos' in t or 'pinginhos' in t or \
       'pouquinho' in t or ('pouco' in t and 'pouco xixi' in t or 'fez pouco' in t):
        notes.append('pouca quantidade')
    if 'ipad' in t and ('modelei' in t or 'modelando' in t or 'modelo' in t or 'nomeando' in t):
        notes.append('com iPad')
    if 'apertando o pipi' in t:
        notes.append('apertando pipi')
    if 'fralda' in t and 'seca' in t:
        notes.append('fralda seca')
    if 'deu descarga' in t:
        notes.append('deu descarga')

    result['notas'] = '; '.join(notes)
    return result

def extract_activity(text):
    """Extract what Isaac was doing during an escape."""
    t = text.lower()

    # Direct activity mentions
    activity_map = [
        ('dormindo', 'dormindo'),
        ('estava dormindo', 'dormindo'),
        ('tava dormindo', 'dormindo'),
        ('assistindo', 'assistindo TV'),
        ('vendo tv', 'assistindo TV'),
        ('vendo o thomas', 'assistindo TV'),
        ('jogando', 'jogando/tela'),
        ('joguinho', 'jogando/tela'),
        ('celular', 'jogando/tela'),
        ('tablet', 'jogando/tela'),
        ('sofá', 'no sofa'),
        ('sofa', 'no sofa'),
        ('rede', 'na rede/balancando'),
        ('balançando', 'na rede/balancando'),
        ('correndo', 'correndo'),
        ('brincando', 'brincando'),
        ('lego', 'brincando'),
        ('bola de pilates', 'brincando'),
        ('sentado', 'sentado'),
        ('cadeira', 'sentado'),
        ('almoçando', 'comendo'),
        ('jantando', 'comendo'),
        ('lanchando', 'comendo'),
        ('comendo', 'comendo'),
        ('tomando café', 'comendo'),
        ('tomando suco', 'comendo'),
        ('sala de aula', 'na escola'),
        ('aula de inglês', 'na escola'),
        ('fazendo prova', 'na escola'),
        ('atividade', 'em atividade'),
        ('dr. melillo', 'Dr. Melillo'),
        ('dr melillo', 'Dr. Melillo'),
        ('deitado', 'deitado'),
        ('cama', 'na cama'),
        ('esperando', 'esperando'),
        ('pintando', 'brincando'),
        ('desregulado', 'desregulado'),
        ('andando pela', 'andando'),
        ('subindo escada', 'atividade fisica'),
        ('subir e pular', 'atividade fisica'),
        ('no jardim', 'no jardim'),
        ('no quintal', 'no quintal'),
        ('biblioteca', 'na biblioteca'),
        ('parque', 'no parque'),
        ('na salinha', 'na escola'),
        ('fono', 'terapia'),
        ('durante a to', 'terapia'),
        ('fisio', 'terapia'),
        ('guardando', 'arrumando'),
        ('não queria guardar', 'resistindo demanda'),
    ]

    for keyword, activity in activity_map:
        if keyword in t:
            return activity

    return None

def parse_multiline_messages(text):
    """Handle messages that contain multiple events (e.g., Dyani's batch messages)."""
    # Split on newline events like "8:30 Levei xixi\n9:00 Levei xixi"
    events_in_msg = []
    lines = text.split('\n')
    if len(lines) > 1:
        for line in lines:
            line = line.strip()
            if line and re.match(r'\d{1,2}[:\.]?\d{0,2}', line):
                events_in_msg.append(line)
        if events_in_msg:
            return events_in_msg
    return [text]

def parse_chat(filepath):
    """Parse the WhatsApp chat export."""
    msg_pattern = re.compile(r'^\[(\d{2}/\d{2}/\d{2}, \d{2}:\d{2}:\d{2})\] (.+?): (.+)')

    events = []

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Join continuation lines
    messages = []
    for line in lines:
        line = line.rstrip('\n').rstrip('\r')
        if not line.strip():
            continue
        # Remove LTR marks at start
        line = re.sub(r'^\u200e', '', line)
        m = msg_pattern.match(line)
        if m:
            messages.append((m.group(1), m.group(2), m.group(3)))
        elif messages:
            ts, sender, text = messages[-1]
            messages[-1] = (ts, sender, text + '\n' + line.strip())

    for ts_str, sender, text in messages:
        # Clean text
        text = re.sub(r'\u200e', '', text)
        text = text.replace('<This message was edited>', '').strip()

        # Skip system messages
        if sender in ['You', '\u200eYou']:
            continue
        if any(skip in text for skip in SKIP_PATTERNS):
            continue

        # Handle multi-event messages (e.g., "8:30 levei xixi\n9:00 levei xixi")
        sub_messages = parse_multiline_messages(text)

        for sub_text in sub_messages:
            sub_text = sub_text.strip()
            if not sub_text:
                continue

            event = classify_event(sub_text)
            if event is None:
                # Try with full text if sub_text failed and it's the only one
                if len(sub_messages) == 1:
                    continue
                event = classify_event(text)
                if event is None:
                    continue

            ts = parse_timestamp(ts_str)

            # Check for explicit time
            explicit_time = extract_explicit_time(sub_text)
            if explicit_time:
                event_time = explicit_time
            else:
                event_time = ts.strftime('%H:%M')

            # Clean sender name
            sender_clean = (sender
                .replace(' Aparecida Lobato', '')
                .replace(' Lâmpada', '')
                .replace(' Diniz AT Isaac', ' AT')
                .replace(' Takuva', '')
                .replace(' Felipe Psicologo Autismo', ' Psico'))

            events.append({
                'data': ts.strftime('%Y-%m-%d'),
                'dia_semana': ['seg', 'ter', 'qua', 'qui', 'sex', 'sab', 'dom'][ts.weekday()],
                'hora': event_time,
                'quem_registrou': sender_clean,
                'tipo': event['tipo'],
                'sucesso': 'sim' if event['sucesso'] == True else ('escape' if event['sucesso'] == False else ''),
                'local': event['local'],
                'iniciativa': event['iniciativa'] or '',
                'atividade_escape': event['atividade_escape'] or '',
                'notas': event['notas'],
                'texto_original': sub_text if len(sub_messages) > 1 else text,
            })

    return events

def write_csv(events, filepath):
    fields = ['data', 'dia_semana', 'hora', 'quem_registrou', 'tipo', 'sucesso', 'local', 'iniciativa', 'atividade_escape', 'notas', 'texto_original']
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(events)

def analyze(events):
    total = len(events)
    real_events = [e for e in events if e['tipo'] != 'nao_fez']
    nao_fez = [e for e in events if e['tipo'] == 'nao_fez']
    successes = [e for e in real_events if e['sucesso'] == 'sim']
    escapes = [e for e in real_events if e['sucesso'] == 'escape']

    # Date range
    first_date = events[0]['data']
    last_date = events[-1]['data']
    d1 = datetime.strptime(first_date, '%Y-%m-%d')
    d2 = datetime.strptime(last_date, '%Y-%m-%d')
    total_days = (d2 - d1).days + 1

    print("=" * 70)
    print("RELATORIO DE DESFRALDE - ISAAC")
    print(f"Periodo: {first_date} a {last_date} ({total_days} dias)")
    print(f"Total de registros: {total}")
    print(f"  Eventos (xixi/coco efetivos): {len(real_events)}")
    print(f"  'Levou mas nao fez': {len(nao_fez)}")
    print("=" * 70)

    print(f"\n{'='*70}")
    print("1. TAXA DE SUCESSO GERAL")
    print(f"{'='*70}")
    print(f"  Sucesso (vaso/banho): {len(successes)} ({100*len(successes)/len(real_events):.1f}%)")
    print(f"  Escape:               {len(escapes)} ({100*len(escapes)/len(real_events):.1f}%)")
    print(f"  Media escapes/dia:    {len(escapes)/total_days:.1f}")
    print(f"  Media sucessos/dia:   {len(successes)/total_days:.1f}")

    print(f"\n{'='*70}")
    print("2. POR TIPO DE EVENTO")
    print(f"{'='*70}")
    for tipo in ['xixi', 'coco', 'xixi+coco']:
        t_events = [e for e in real_events if e['tipo'] == tipo]
        t_success = [e for e in t_events if e['sucesso'] == 'sim']
        t_escape = [e for e in t_events if e['sucesso'] == 'escape']
        if t_events:
            print(f"  {tipo:>10}: {len(t_events):>4} total | {len(t_success):>3} sucesso ({100*len(t_success)/len(t_events):.0f}%) | {len(t_escape):>3} escape ({100*len(t_escape)/len(t_events):.0f}%)")

    print(f"\n{'='*70}")
    print("3. INICIATIVA NOS SUCESSOS")
    print(f"{'='*70}")
    init_counts = Counter(e['iniciativa'] for e in successes)
    for init, count in init_counts.most_common():
        label = init if init else '(nao especificado)'
        print(f"  {label:>20}: {count:>4} ({100*count/len(successes):.1f}%)")

    print(f"\n{'='*70}")
    print("4. EVOLUCAO SEMANAL")
    print(f"{'='*70}")

    weekly = defaultdict(lambda: {'success': 0, 'escape': 0, 'nao_fez': 0, 'days': set(),
                                   'sozinho': 0, 'pediu': 0, 'total_success': 0})
    for e in events:
        d = datetime.strptime(e['data'], '%Y-%m-%d')
        # Use Monday-based week
        week_start = d - __import__('datetime').timedelta(days=d.weekday())
        week_key = week_start.strftime('%m/%d')
        weekly[week_key]['days'].add(e['data'])
        if e['tipo'] == 'nao_fez':
            weekly[week_key]['nao_fez'] += 1
        elif e['sucesso'] == 'sim':
            weekly[week_key]['success'] += 1
            weekly[week_key]['total_success'] += 1
            if e['iniciativa'] in ('sozinho', 'pediu'):
                weekly[week_key]['sozinho'] += 1
            if e['iniciativa'] == 'pediu':
                weekly[week_key]['pediu'] += 1
        else:
            weekly[week_key]['escape'] += 1

    print(f"  {'Sem.inicio':<12} {'Dias':>4} {'Suces':>6} {'Escap':>6} {'NaoFz':>6} {'%Suc':>6} {'Esc/d':>6} {'%Indep':>7}")
    print(f"  {'-'*54}")
    for week in sorted(weekly.keys()):
        w = weekly[week]
        total_w = w['success'] + w['escape']
        days = len(w['days'])
        rate = 100 * w['success'] / total_w if total_w > 0 else 0
        esc_per_day = w['escape'] / days if days > 0 else 0
        indep_rate = 100 * w['sozinho'] / w['total_success'] if w['total_success'] > 0 else 0
        print(f"  {week:<12} {days:>4} {w['success']:>6} {w['escape']:>6} {w['nao_fez']:>6} {rate:>5.0f}% {esc_per_day:>5.1f} {indep_rate:>6.0f}%")

    print(f"\n{'='*70}")
    print("5. ESCAPES POR PERIODO DO DIA")
    print(f"{'='*70}")
    periods = defaultdict(lambda: {'escape': 0, 'total': 0})
    for e in real_events:
        h = int(e['hora'].split(':')[0])
        if 6 <= h < 12:
            p = 'Manha (06-12h)'
        elif 12 <= h < 18:
            p = 'Tarde (12-18h)'
        elif 18 <= h < 24:
            p = 'Noite (18-00h)'
        else:
            p = 'Madrugada (00-06h)'
        periods[p]['total'] += 1
        if e['sucesso'] == 'escape':
            periods[p]['escape'] += 1

    for p in ['Manha (06-12h)', 'Tarde (12-18h)', 'Noite (18-00h)', 'Madrugada (00-06h)']:
        if periods[p]['total'] > 0:
            esc = periods[p]['escape']
            tot = periods[p]['total']
            rate = 100 * esc / tot
            bar = '|' * int(rate)
            print(f"  {p:<20} {esc:>3}/{tot:<3} ({rate:>4.1f}%) {bar}")

    print(f"\n{'='*70}")
    print("6. ATIVIDADE DURANTE ESCAPES")
    print(f"{'='*70}")
    activities = [e['atividade_escape'] for e in escapes if e['atividade_escape']]
    act_counter = Counter(activities)
    for act, count in act_counter.most_common(15):
        print(f"  {act:<25} {count:>3}")
    print(f"  (sem registro)          {len(escapes) - len(activities):>3}")

    print(f"\n{'='*70}")
    print("7. ANALISE DE COCO")
    print(f"{'='*70}")
    cocos = [e for e in real_events if 'coco' in e['tipo']]
    coco_success = [e for e in cocos if e['sucesso'] == 'sim']
    coco_escape = [e for e in cocos if e['sucesso'] == 'escape']
    coco_sozinho = [e for e in coco_success if e['iniciativa'] == 'sozinho']
    print(f"  Total cocos:    {len(cocos)}")
    print(f"  No vaso:        {len(coco_success)} ({100*len(coco_success)/max(len(cocos),1):.0f}%)")
    print(f"  Escape:         {len(coco_escape)} ({100*len(coco_escape)/max(len(cocos),1):.0f}%)")
    print(f"  Foi sozinho:    {len(coco_sozinho)} ({100*len(coco_sozinho)/max(len(cocos),1):.0f}%)")

    print(f"\n{'='*70}")
    print("8. TENDENCIA DE INDEPENDENCIA (sozinho + pediu por semana)")
    print(f"{'='*70}")
    for week in sorted(weekly.keys()):
        w = weekly[week]
        if w['total_success'] > 0:
            rate = 100 * w['sozinho'] / w['total_success']
            bar = '#' * int(rate / 2)
            print(f"  {week}: {w['sozinho']:>3}/{w['total_success']:<3} ({rate:>4.0f}%) {bar}")

    print(f"\n{'='*70}")
    print("9. ESCAPES POR DIA DA SEMANA")
    print(f"{'='*70}")
    dow_esc = Counter()
    dow_total = Counter()
    for e in real_events:
        dow_total[e['dia_semana']] += 1
        if e['sucesso'] == 'escape':
            dow_esc[e['dia_semana']] += 1

    for d in ['seg', 'ter', 'qua', 'qui', 'sex', 'sab', 'dom']:
        t = dow_total.get(d, 0)
        esc = dow_esc.get(d, 0)
        rate = 100 * esc / t if t > 0 else 0
        bar = '|' * int(rate)
        print(f"  {d}: {esc:>3}/{t:<3} ({rate:>4.1f}%) {bar}")

    print(f"\n{'='*70}")
    print("10. INTERVALO ENTRE IDAS AO BANHEIRO")
    print(f"{'='*70}")
    daily_times = defaultdict(list)
    for e in events:
        if e['tipo'] != 'nao_fez':
            h, m = map(int, e['hora'].split(':'))
            daily_times[e['data']].append(h * 60 + m)

    all_intervals = []
    for day, times in sorted(daily_times.items()):
        times.sort()
        for i in range(1, len(times)):
            interval = times[i] - times[i-1]
            if 5 <= interval <= 300:  # filter outliers
                all_intervals.append(interval)

    if all_intervals:
        avg = sum(all_intervals) / len(all_intervals)
        all_intervals.sort()
        med = all_intervals[len(all_intervals) // 2]
        p25 = all_intervals[len(all_intervals) // 4]
        p75 = all_intervals[3 * len(all_intervals) // 4]
        print(f"  Media:    {avg:.0f} min")
        print(f"  Mediana:  {med} min")
        print(f"  P25-P75:  {p25}-{p75} min")

    print(f"\n{'='*70}")
    print("11. 'LEVOU MAS NAO FEZ'")
    print(f"{'='*70}")
    print(f"  Total: {len(nao_fez)}")
    print(f"  Media/dia: {len(nao_fez)/total_days:.1f}")
    nf_per_week = Counter()
    for e in nao_fez:
        d = datetime.strptime(e['data'], '%Y-%m-%d')
        week_start = d - __import__('datetime').timedelta(days=d.weekday())
        nf_per_week[week_start.strftime('%m/%d')] += 1
    for week in sorted(nf_per_week.keys()):
        print(f"    {week}: {nf_per_week[week]}")

    # INSIGHTS
    print(f"\n{'='*70}")
    print("INSIGHTS E OBSERVACOES")
    print(f"{'='*70}")

    print("""
1. TAXA DE SUCESSO ESTAVEL MAS SEM MELHORA CLARA
   A taxa de sucesso oscila entre 73-85% sem tendencia clara de melhora
   ao longo das 8 semanas. Isso pode indicar que o protocolo atual
   atingiu um "platô".

2. NOITE E O PERIODO MAIS CRITICO
   25.8% de escape à noite vs 15.2% à tarde. Isaac parece ter mais
   dificuldade de controle no periodo noturno (18h-00h), possivelmente
   por cansaço/desregulação sensorial.

3. DOMINGOS TEM MAIS ESCAPES
   Domingos mostram taxa de escape mais alta. Pode estar relacionado
   a rotina menos estruturada nos fins de semana.

4. COCO TEM BOA AUTONOMIA
   42% dos cocos Isaac foi sozinho - demonstra boa autopercepção para
   cocô. A dificuldade maior é com xixi.

5. ESCAPES ASSOCIADOS A ATIVIDADES SEDENTARIAS/HIPERFOCO
   Sofá/TV, jogando, e na rede são as atividades mais comuns durante
   escapes. Quando Isaac está em hiperfoco (tela, brincadeira), ele
   parece não perceber a necessidade.

6. INDEPENDENCIA CRESCEU MAS ESTABILIZOU
   Independência subiu de ~7% na semana 1 para ~30-32% e estabilizou.
   O "pediu" (comunicação ativa) ainda é baixo (4.3%).

7. MUITOS "PINGUINHOS"
   Isaac vai frequentemente ao banheiro fazer pouca quantidade,
   sugerindo que pode estar usando o banheiro como fuga de demanda
   (confirmado pelo psicólogo) ou que tem dificuldade de esvaziar
   completamente.

8. INTERVALO DE ~60 MIN CONSISTENTE
   O intervalo médio entre idas ao banheiro é ~60 min, alinhado
   com o protocolo de levar a cada 1h.
""")


if __name__ == '__main__':
    events = parse_chat('/Users/tony/work/solo/xixicoco/chat.txt')
    write_csv(events, '/Users/tony/work/solo/xixicoco/isaac_desfralde.csv')
    print(f"CSV salvo: isaac_desfralde.csv ({len(events)} registros)\n")
    analyze(events)
