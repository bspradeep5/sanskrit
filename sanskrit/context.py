# -*- coding: utf-8 -*-
import imp
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from .schema import Base, EnumBase, GenderGroup


class Context(object):

    """The package context. In addition to storing basic config information,
    such as the database URI or paths to various data files, a :class:`Context`
    also constructs a :class:`~sqlalchemy.orm.session.Session` class for
    connecting to the database.

    You can populate a context in several ways. For example, you can pass a
    path to a Python module::

        context = Context('project/config.py')

    If you do so, only uppercase keys will be stored in the context. This lets
    you use lowercase variables as temporary values.

    Config values are stored internally as a :class:`dict`, so you can always
    just use ordinary :class:`dict` methods::

        context.config['FOO'] = 'baz'

    :param config: an object to read from. If this is a string, treat
                   `config` as a module path and load values from that
                   module. Otherwise, treat `config` as a dictionary.
    """

    def __init__(self, config=None, connect=True):
        #: A :class:`dict` of various settings. By convention, all keys are
        #: uppercase. These are used to create :attr:`engine` and
        #: :attr:`session`.
        self.config = {}

        #: The :class:`~sqlalchemy.engine.base.Engine` that underlies
        #: the :attr:`session`.
        self.engine = None

        #: A :class:`~sqlalchemy.orm.session.Session` class.
        self.session = None

        if isinstance(config, basestring):
            filepath = config
            config = imp.new_module('config')
            config.__file__ = filepath
            try:
                execfile(filepath, config.__dict__)
            except IOError, e:
                e.strerror = 'Cannot load config file: %s' % e.strerror
                raise

        try:
            config = config or {}
            for key in config:
                if key.isupper():
                    self.config[key] = config[key]
        except TypeError:
            for key in dir(config):
                if key.isupper():
                    self.config[key] = getattr(config, key)

        def default(name, *args):
            path = os.path.join(self.config['DATA_PATH'], 'lang', *args)
            self.config.setdefault(name, path)

        default('ADJECTIVE_STEMS', 'adjective-stems.csv')
        default('ENUMS', 'enums.yml')
        default('GERUNDS', 'gerunds.csv')
        default('INDECLINABLES', 'indeclinables.yml')
        default('INFINITIVES', 'infinitives.csv')
        default('IRREGULAR_ADJECTIVES', 'irregular-adjectives.yml')
        default('IRREGULAR_NOUNS', 'irregular-nouns.yml')
        default('MODIFIED_ROOTS', 'modified-roots.yml')
        default('NOMINAL_ENDINGS', 'nominal-endings.yml')
        default('NOUN_STEMS', 'noun-stems.csv')
        default('PARTICIPLE_STEMS', 'participle-stems.csv')
        default('PREFIX_GROUPS', 'prefix-groups.yml')
        default('PREFIXED_ROOTS', 'prefixed-roots.yml')
        default('PRONOUNS', 'pronouns.yml')
        default('ROOTS', 'roots.yml')
        default('SANDHI', 'sandhi.yml')
        default('VERB_ENDINGS', 'verb-endings.yml')
        default('VERB_PREFIXES', 'verb-prefixes.yml')
        default('VERB_STEMS', 'verb-stems.yml')
        default('VERBS', 'verbs.csv')

        if connect and 'DATABASE_URI' in self.config:
            self.connect()

    def build(self):
        """Build all data."""
        from sanskrit import setup
        setup.run(self)

    def connect(self):
        """Connect to the database."""
        self.engine = create_engine(self.config['DATABASE_URI'])
        self.session = scoped_session(sessionmaker(autocommit=False,
                                                   autoflush=False,
                                                   bind=self.engine))

    def create_all(self):
        """Create tables for every model in `sanskrit.schema`."""
        metadata = Base.metadata
        extant = {t.name for t in metadata.tables.values() if t.exists(self.engine)}
        metadata.create_all(self.engine)
        for name in metadata.sorted_tables:
            if name not in extant:
                print '  [ c ] {0}'.format(name)

    def drop_all(self):
        """Drop all tables defined in `sanskrit.schema`."""
        Base.metadata.drop_all(self.engine)

    def _build_enums(self):
        """Fetch and store enumerated data."""
        self._enum_id = {}
        self._enum_abbr = {}
        self._gender_set = {}

        session = self.session
        for cls in EnumBase.__subclasses__():
            key = cls.__tablename__
            self._enum_id[key] = enum_id = {}
            self._enum_abbr[key] = enum_abbr = {}
            for item in session.query(cls).all():
                enum_id[item.name] = enum_id[item.abbr] = item.id
                enum_abbr[item.id] = enum_abbr[item.name] = item.abbr

        for group in session.query(GenderGroup):
            member_ids = set([x.id for x in group.members])
            self._gender_set[group.id] = member_ids

        session.remove()

    @property
    def enum_id(self):
        """Maps a name or abbreviation to an ID."""
        try:
            return self._enum_id
        except AttributeError:
            self._build_enums()
            return self._enum_id

    @property
    def enum_abbr(self):
        """Maps an ID or name to an abbreviation."""
        try:
            return self._enum_abbr
        except AttributeError:
            self._build_enums()
            return self._enum_abbr

    @property
    def gender_set(self):
        try:
            return self._gender_set
        except AttributeError:
            self._build_enums()
            return self._gender_set
