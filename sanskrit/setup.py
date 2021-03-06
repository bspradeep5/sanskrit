"""
sanskrit.setup
~~~~~~~~~~~~~~

Setup code for various Sanskrit data.
"""

import sys

import yaml

from sanskrit import util
from sanskrit.schema import *

# Populated in `add_enums`
ENUM = {}


# Miscellaneous
# -------------

def add_tags(ctx):
    session = ctx.session
    for key in dir(Tag):
        if key.isupper():
            id = getattr(Tag, key)
            session.add(Tag(id=id, name=key.lower()))

    session.commit()
    session.close()


def add_enums(ctx):
    """Add enumerated data to the database. Among others, this includes:

    - persons
    - numbers
    - modes
    - voices
    - genders
    - cases

    and any other data with small, known limits.
    """

    session = ctx.session
    classes = [Modification, VClass, Person, Number, Mode, Voice,
               Gender, Case, SandhiType]
    names = [c.__name__ for c in classes]
    mapper = dict(zip(names, classes))

    # First pass: ordinary enums
    with open(ctx.config['ENUMS']) as f:
        for enum in yaml.load(f):
            enum_name = enum['name']
            cls = mapper.get(enum_name, None)
            if cls is None:
                continue

            enum_abbr = cls.__tablename__
            ENUM[enum_abbr] = {}

            for item in enum['items']:
                item_name = item['name']
                abbr = item['abbr']
                e = cls(name=item_name, abbr=abbr)

                session.add(e)
                session.flush()
                ENUM[enum_abbr][abbr] = e.id

            util.tick(cls.__name__)

    session.commit()

    # Second pass: gender groups
    with open(ctx.config['ENUMS']) as f:
        for enum in yaml.load(f):
            enum_name = enum['name']
            cls = GenderGroup
            if enum_name != cls.__name__:
                continue

            enum_abbr = cls.__tablename__
            ENUM[enum_abbr] = {}

            for item in enum['items']:
                e = cls(name=item['name'], abbr=item['abbr'])
                session.add(e)
                session.flush()

                e.members = [ENUM['gender'][x] for x in item['members']]

                abbr = item['abbr']
                ENUM[enum_abbr][abbr] = e.id

            util.tick(cls.__name__)

    session.commit()
    session.close()


def add_sandhi(ctx):
    """Add sandhi rules to the database."""
    session = ctx.session
    stype = ENUM['sandhi_type']

    with open(ctx.config['SANDHI']) as f:
        for ruleset in yaml.load_all(f):
            rule_type = ruleset['type']
            util.tick(rule_type)
            for rule in ruleset['rules']:
                rule['rule_type'] = stype[rule_type]
                s = SandhiRule(**rule)
                session.add(s)

    session.commit()
    session.close()


def add_indeclinables(ctx):
    """Add indeclinables to the database."""
    session = ctx.session

    with open(ctx.config['INDECLINABLES']) as f:
        for i, name in enumerate(yaml.load(f)):
            ind = Indeclinable(name=name)
            session.add(ind)
            if i % 200 == 0:
                util.tick(name)

    session.commit()
    session.close()


# Verbal data
# ------------

def add_verb_prefixes(ctx):
    """Add verb prefixes to the database."""
    session = ctx.session
    prefix_map = {}

    with open(ctx.config['VERB_PREFIXES']) as f:
        for group in yaml.load_all(f):
            util.tick(group['name'])
            for name in group['items']:
                prefix = VerbPrefix(name=name)
                session.add(prefix)
                session.flush()
                prefix_map[name] = prefix.id

    session.commit()
    session.close()
    return prefix_map


def add_verb_endings(ctx):
    """Add verb endings to the database."""
    session = ctx.session

    with open(ctx.config['VERB_ENDINGS']) as f:
        person = ENUM['person']
        number = ENUM['number']
        mode = ENUM['mode']
        voice = ENUM['voice']

        for group in yaml.load_all(f):
            mode_id = mode[group['mode']]
            voice_id = voice[group['voice']]
            category = group['category']

            for row in group['endings']:
                kw = {
                    'name': row['name'],
                    'category': category,
                    'person_id': person[row['person']],
                    'number_id': number[row['number']],
                    'mode_id': mode_id,
                    'voice_id': voice_id,
                    }
                ending = VerbEnding(**kw)
                session.add(ending)
                session.flush()
            util.tick((group['mode'], group['voice'], category))

    session.commit()
    session.close()


def add_roots(ctx):
    """Add verb roots to the database."""

    session = ctx.session
    vclass = ENUM['vclass']
    voice = ENUM['voice']

    root_map = {}  # (name, hom) -> id
    with open(ctx.config['ROOTS']) as f:
        for i, item in enumerate(yaml.load_all(f)):
            name = item['name']
            paradigms = item['paradigms']

            root = Root(name=name)
            session.add(root)
            session.flush()

            for row in paradigms:
                paradigm = Paradigm(root_id=root.id,
                                    vclass_id=vclass[row[0]],
                                    voice_id=voice[row[1]])
                session.add(paradigm)

            hom = item.get('hom', None)
            root_map[(name, hom)] = root.id

            if i % 100 == 0:
                util.tick(name)

    session.commit()
    session.close()
    return root_map


def add_prefixed_roots(ctx, root_map=None, prefix_map=None):
    """Add prefixed roots to the database."""

    homs = [None] + [str(i) for i in range(1, 10)]

    # Contains roots that weren't added by `add_roots`.
    missed = set()

    with open(ctx.config['PREFIXED_ROOTS']) as f:
        for i, item in enumerate(yaml.load_all(f)):
            name = item['name']
            basis = item['basis']
            hom = item.get('hom', None)
            prefixes = item['prefixes']

            basis_id = None
            try:
                basis_id = root_map[(basis, hom)]
            except KeyError:
                for hom in homs:
                    try:
                        basis_id = root_map[(basis, hom)]
                    except KeyError:
                        pass

            if basis_id is None:
                candidates = [k for k in root_map.keys() if k[0] == basis]
                print 'SKIPPED:', name, basis, candidates
                missed.add(basis)
                continue

            prefixed_root = PrefixedRoot(name=name, basis_id=basis_id)
            session.add(prefixed_root)
            session.flush()

            for prefix in prefixes:
                pass

            if i % 100 == 0:
                util.tick(name)

    session.commit()
    session.close()
    print missed


def add_modified_roots(ctx):
    """Add modified roots to the database."""


def add_verbs(ctx, root_map=None):
    """Add inflected verbs to the database."""

    session = ctx.session
    vclass = ENUM['vclass']
    person = ENUM['person']
    number = ENUM['number']
    mode = ENUM['mode']
    voice = ENUM['voice']
    skipped = set()
    i = 0

    for row in util.read_csv(ctx.config['VERBS']):
        root = row['root']
        hom = row['hom']

        try:
            root_id = root_map[(root, hom)]
        except KeyError:
            skipped.add((root, hom))
            continue

        data = {
            'name': row['name'],
            'root_id': root_id,
            'vclass_id': vclass[row['vclass']] if row['vclass'] else None,
            'person_id': person[row['person']],
            'number_id': number[row['number']],
            'mode_id': mode[row['mode']],
            'voice_id': voice[row['voice']]
        }
        session.add(Verb(**data))

        i += 1
        if i % 1000 == 0:
            util.tick(row['name'])
            session.commit()

    session.commit()
    session.close()
    print 'Skipped', len(skipped), 'roots.'


def add_verbal_indeclinables(ctx, root_map=None):
    session = ctx.session
    root_map = root_map or {}
    skipped = set()

    items = [
        ('GERUNDS', Gerund),
        ('INFINITIVES', Infinitive),
        ]

    for file_key, cls in items:
        for row in util.read_csv(ctx.config[file_key]):
            root = row['root']
            hom = row['hom']

            try:
                root_id = root_map[(root, hom)]
            except KeyError:
                skipped.add((root, hom))
                continue

            datum = {
                'name': row['name'],
                'root_id': root_id
                }
            session.add(cls(**datum))
    session.commit()


def add_participle_stems(ctx, root_map=None):
    """"""

    session = ctx.session
    root_map = root_map or {}
    mode = ENUM['mode']
    voice = ENUM['voice']
    skipped = set()
    i = 0

    for row in util.read_csv(ctx.config['PARTICIPLE_STEMS']):
        root = row['root']
        hom = row['hom']

        try:
            root_id = root_map[(root, hom)]
        except KeyError:
            skipped.add((root, hom))
            continue

        data = {
            'name': row['name'],
            'root_id': root_id,
            'mode_id': mode[row['mode']],
            'voice_id': voice[row['voice']]
            }

        session.add(ParticipleStem(**data))

        i += 1
        if i % 100 == 0:
            util.tick(row['name'])
            session.commit()

    session.commit()
    session.close()
    print 'Skipped', len(skipped), 'roots.'


def add_verbal(ctx):
    """Add all verb data to the database, including:

    - roots
    - prefixed roots
    - modified roots
    - prefixed modified roots
    - inflected verbs
    - participles
    - gerunds
    - infinitives
    """

    util.heading('Verb prefixes')
    prefixes = add_verb_prefixes(ctx)

    util.heading('Verb endings')
    add_verb_endings(ctx)

    util.heading('Roots and paradigms')
    roots = add_roots(ctx)

    util.heading('Verbs')
    add_verbs(ctx, roots)

    util.heading('Participle stems')
    add_participle_stems(ctx, roots)

    util.heading('Verbal indeclinables')
    add_verbal_indeclinables(ctx, roots)

    return

    util.heading('Prefixed roots')
    add_prefixed_roots(ctx, root_map=roots, prefix_map=prefixes)


# Nominal data
# ------------

def add_nominals(ctx):
    util.heading('Nominal endings')
    add_nominal_endings(ctx)

    util.heading('Noun stems')
    add_noun_stems(ctx)
    util.heading('Irregular nouns')
    add_irregular_nouns(ctx)

    util.heading('Adjective stems')
    add_adjective_stems(ctx)
    util.heading('Irregular adjectives')
    add_irregular_adjectives(ctx)

    util.heading('Pronouns')
    add_pronouns(ctx)


def add_nominal_endings(ctx):
    """Add nominal endings to the database."""
    session = ctx.session
    with open(ctx.config['NOMINAL_ENDINGS']) as f:
        gender = ENUM['gender']
        case = ENUM['case']
        number = ENUM['number']

        for group in yaml.load_all(f):
            stem_type = group['stem']
            for row in group['endings']:
                kw = {
                    'name': row['name'],
                    'stem_type': stem_type,
                    'gender_id': gender[row['gender']],
                    'case_id': case.get(row.get('case')),
                    'number_id': number.get(row.get('number')),
                    'compounded': row.get('compounded', False)
                    }
                ending = NominalEnding(**kw)
                session.add(ending)
                session.flush()
            util.tick(stem_type)

    session.commit()
    session.close()


def add_noun_stems(ctx):
    """Add regular noun stems to the database."""

    conn = ctx.engine.connect()
    ins = NounStem.__table__.insert()
    gender_group = ENUM['gender_group']
    pos_id = Tag.NOUN

    buf = []
    i = 0
    for noun in util.read_csv(ctx.config['NOUN_STEMS']):
        name = noun['name']
        genders_id = gender_group[noun['genders']]
        buf.append({
            'name': name,
            'pos_id': pos_id,
            'genders_id': genders_id,
            })

        i += 1
        if i % 500 == 0:
            util.tick(name)
            conn.execute(ins, buf)
            buf = []

    if buf:
        conn.execute(ins, buf)


def add_irregular_nouns(ctx):
    """Add irregular nouns to the database."""

    session = ctx.session
    gender_group = ENUM['gender_group']
    gender = ENUM['gender']
    case = ENUM['case']
    number = ENUM['number']

    with open(ctx.config['IRREGULAR_NOUNS']) as f:
        for noun in yaml.load_all(f):
            genders_id = gender_group[noun['genders']]
            stem = NounStem(name=noun['name'], genders_id=genders_id)
            session.add(stem)
            session.flush()

            # Mark the stem as irregular
            complete = noun['complete']
            irreg = StemIrregularity(stem=stem, fully_described=complete)
            session.add(irreg)
            session.flush()

            util.tick(stem.name)

            for form in noun['forms']:
                name = form['name']
                gender_id = gender[form['gender']]
                case_id = case[form['case']]
                number_id = number[form['number']]

                result = Noun(stem=stem, name=name, gender_id=gender_id,
                              case_id=case_id, number_id=number_id)
                session.add(result)
                session.flush()

    session.commit()
    session.close()


def add_adjective_stems(ctx):
    """Add adjective stems to the database."""

    conn = ctx.engine.connect()
    ins = AdjectiveStem.__table__.insert()
    pos_id = Tag.ADJECTIVE

    buf = []
    i = 0
    for adj in util.read_csv(ctx.config['ADJECTIVE_STEMS']):
        name = adj['name']
        buf.append({
            'name': name,
            'pos_id': pos_id,
            })

        i += 1
        if i % 500 == 0:
            util.tick(name)
            conn.execute(ins, buf)
            buf = []

    if buf:
        conn.execute(ins, buf)


def add_irregular_adjectives(ctx):
    """Add regular irregular adjectives to the database."""

    session = ctx.session
    gender = ENUM['gender']
    case = ENUM['case']
    number = ENUM['number']

    with open(ctx.config['IRREGULAR_ADJECTIVES']) as f:
        for adj in yaml.load_all(f):
            stem = AdjectiveStem(name=adj['name'])
            session.add(stem)
            session.flush()

            # Mark the stem as irregular
            complete = adj['complete']
            irreg = StemIrregularity(stem=stem, fully_described=complete)
            session.add(irreg)
            session.flush()

            util.tick(stem.name)

            for form in adj['forms']:
                name = form['name']
                gender_id = gender[form['gender']]
                case_id = case[form['case']]
                number_id = number[form['number']]

                result = Adjective(stem=stem, name=name, gender_id=gender_id,
                                   case_id=case_id, number_id=number_id)
                session.add(result)

    session.commit()
    session.close()


def add_pronouns(ctx):
    """Add pronouns to the database."""

    session = ctx.session
    gender_group = ENUM['gender_group']
    gender = ENUM['gender']
    case = ENUM['case']
    number = ENUM['number']

    with open(ctx.config['PRONOUNS']) as f:
        for pronoun in yaml.load_all(f):
            genders_id = gender_group[pronoun['genders']]
            stem = PronounStem(name=pronoun['name'], genders_id=genders_id)
            session.add(stem)
            session.flush()
            util.tick(stem.name)

            for item in pronoun['forms']:
                name = item['name']
                gender_id = gender[item['gender']]
                case_id = case[item['case']]
                number_id = number[item['number']]

                result = Pronoun(stem=stem, name=name, gender_id=gender_id,
                                 case_id=case_id, number_id=number_id)
                session.add(result)
                session.flush()

    session.commit()
    session.close()


# Main
# ----

def run(ctx):
    """Create and populate tables in the database."""
    ctx.drop_all()
    ctx.create_all()

    functions = [
        ('Tags', add_tags),
        ('Enumerated data', add_enums),
        ('Sandhi', add_sandhi),
        ('Indeclinables', add_indeclinables),
        ('Verbal data', add_verbal),
        ('Nominal data', add_nominals),
        ]

    for name, f in functions:
        util.heading(name, '~')
        f(ctx)


if __name__ == '__main__':
    ctx = Context(sys.argv[1])
    run(ctx)
