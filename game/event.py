from game.operation import *

DIFFICULTY_LOG_BASE = 1.5


class Event:
    silent = False
    informational = False
    is_awacs_enabled = False
    operation = None  # type: Operation
    difficulty = 1  # type: int
    BONUS_BASE = 0

    def __init__(self, attacker_name: str, defender_name: str, from_cp: ControlPoint, to_cp: ControlPoint, game):
        self.attacker_name = attacker_name
        self.defender_name = defender_name
        self.to_cp = to_cp
        self.from_cp = from_cp
        self.game = game

    @property
    def is_player_attacking(self) -> bool:
        return self.attacker_name == self.game.player

    @property
    def enemy_cp(self) -> ControlPoint:
        if self.attacker_name == self.game.player:
            return self.to_cp
        else:
            return self.from_cp

    @property
    def threat_description(self) -> str:
        return ""

    def bonus(self) -> int:
        return math.ceil(math.log(self.difficulty, DIFFICULTY_LOG_BASE) * self.BONUS_BASE)

    def is_successfull(self, debriefing: Debriefing) -> bool:
        return self.operation.is_successfull(debriefing)

    def generate(self):
        self.operation.is_awacs_enabled = self.is_awacs_enabled
        self.operation.prepare(self.game.theater.terrain, is_quick=False)
        self.operation.generate()
        self.operation.mission.save("build/nextturn.miz")

    def generate_quick(self):
        self.operation.is_awacs_enabled = self.is_awacs_enabled
        self.operation.prepare(self.game.theater.terrain, is_quick=True)
        self.operation.generate()
        self.operation.mission.save('build/nextturn_quick.miz')

    def commit(self, debriefing: Debriefing):
        for country, losses in debriefing.destroyed_units.items():
            if country == self.attacker_name:
                cp = self.from_cp
            else:
                cp = self.to_cp

            cp.base.commit_losses(losses)

    def skip(self):
        pass


class GroundInterceptEvent(Event):
    BONUS_BASE = 3
    TARGET_AMOUNT_FACTOR = 2
    TARGET_VARIETY = 2
    STRENGTH_INFLUENCE = 0.3
    SUCCESS_TARGETS_HIT_PERCENTAGE = 0.5

    targets = None  # type: db.ArmorDict

    def __str__(self):
        return "Ground intercept from {} at {}".format(self.from_cp, self.to_cp)

    def is_successfull(self, debriefing: Debriefing):
        total_targets = sum(self.targets.values())
        destroyed_targets = 0
        for unit, count in debriefing.destroyed_units[self.defender_name].items():
            if unit in self.targets:
                destroyed_targets += count

        return (float(destroyed_targets) / float(total_targets)) >= self.SUCCESS_TARGETS_HIT_PERCENTAGE

    def commit(self, debriefing: Debriefing):
        super(GroundInterceptEvent, self).commit(debriefing)

        if self.from_cp.captured:
            if self.is_successfull(debriefing):
                self.to_cp.base.affect_strength(-self.STRENGTH_INFLUENCE)
            else:
                self.to_cp.base.affect_strength(+self.STRENGTH_INFLUENCE)
        else:
            assert False

    def skip(self):
        if not self.to_cp.captured:
            self.to_cp.base.affect_strength(+0.1)
        else:
            pass

    def player_attacking(self, strikegroup: db.PlaneDict, clients: db.PlaneDict):
        suitable_unittypes = db.find_unittype(PinpointStrike, self.defender_name)
        random.shuffle(suitable_unittypes)
        unittypes = suitable_unittypes[:self.TARGET_VARIETY]
        typecount = max(math.floor(self.difficulty * self.TARGET_AMOUNT_FACTOR), 1)
        self.targets = {unittype: typecount for unittype in unittypes}

        op = GroundInterceptOperation(game=self.game,
                                      attacker_name=self.attacker_name,
                                      defender_name=self.defender_name,
                                      attacker_clients=clients,
                                      defender_clients={},
                                      from_cp=self.from_cp,
                                      to_cp=self.to_cp)
        op.setup(target=self.targets,
                 strikegroup=strikegroup)

        self.operation = op


class InterceptEvent(Event):
    BONUS_BASE = 5
    STRENGTH_INFLUENCE = 0.3
    GLOBAL_STRENGTH_INFLUENCE = 0.3
    AIRDEFENSE_COUNT = 3

    transport_unit = None  # type: FlyingType

    def __str__(self):
        return "Intercept from {} at {}".format(self.from_cp, self.to_cp)

    @property
    def threat_description(self):
        return "{} aircraft".format(self.enemy_cp.base.scramble_count())

    def is_successfull(self, debriefing: Debriefing):
        units_destroyed = debriefing.destroyed_units[self.defender_name].get(self.transport_unit, 0)
        if self.from_cp.captured:
            return units_destroyed > 0
        else:
            return units_destroyed == 0

    def commit(self, debriefing: Debriefing):
        super(InterceptEvent, self).commit(debriefing)

        if self.attacker_name == self.game.player:
            if self.is_successfull(debriefing):
                self.to_cp.base.affect_strength(-self.STRENGTH_INFLUENCE)
            else:
                self.from_cp.base.affect_strength(-self.STRENGTH_INFLUENCE)
        else:
            # enemy attacking
            if self.is_successfull(debriefing):
                self.from_cp.base.affect_strength(-self.STRENGTH_INFLUENCE)
            else:
                self.to_cp.base.affect_strength(-self.STRENGTH_INFLUENCE)

    def skip(self):
        if self.to_cp.captured:
            self.to_cp.base.affect_strength(-self.STRENGTH_INFLUENCE)

    def player_attacking(self, interceptors: db.PlaneDict, clients: db.PlaneDict):
        escort = self.to_cp.base.scramble_sweep()

        self.transport_unit = random.choice(db.find_unittype(Transport, self.defender_name))
        assert self.transport_unit is not None

        airdefense_unit = db.find_unittype(AirDefence, self.defender_name)[-1]
        op = InterceptOperation(game=self.game,
                                attacker_name=self.attacker_name,
                                defender_name=self.defender_name,
                                attacker_clients=clients,
                                defender_clients={},
                                from_cp=self.from_cp,
                                to_cp=self.to_cp)

        op.setup(escort=escort,
                 transport={self.transport_unit: 1},
                 airdefense={airdefense_unit: self.AIRDEFENSE_COUNT},
                 interceptors=interceptors)

        self.operation = op

    def player_defending(self, escort: db.PlaneDict, clients: db.PlaneDict):
        interceptors = self.from_cp.base.scramble_interceptors()

        self.transport_unit = random.choice(db.find_unittype(Transport, self.defender_name))
        assert self.transport_unit is not None

        op = InterceptOperation(game=self.game,
                                attacker_name=self.attacker_name,
                                defender_name=self.defender_name,
                                attacker_clients={},
                                defender_clients=clients,
                                from_cp=self.from_cp,
                                to_cp=self.to_cp)

        op.setup(escort=escort,
                 transport={self.transport_unit: 1},
                 interceptors=interceptors,
                 airdefense={})

        self.operation = op


class CaptureEvent(Event):
    silent = True
    BONUS_BASE = 7
    STRENGTH_RECOVERY = 0.35

    def __str__(self):
        return "Attack from {} to {}".format(self.from_cp, self.to_cp)

    @property
    def threat_description(self):
        descr = "{} aircraft + CAS, {} vehicles".format(
            self.enemy_cp.base.scramble_count(),
            self.enemy_cp.base.assemble_count()
        )

        if self.is_player_attacking:
            descr += ", {} AA".format(self.enemy_cp.base.assemble_aa_count())

        return descr

    def is_successfull(self, debriefing: Debriefing):
        alive_attackers = sum(debriefing.alive_units[self.attacker_name].values())
        alive_defenders = sum(debriefing.alive_units[self.defender_name].values())
        attackers_success = alive_attackers > alive_defenders
        if self.from_cp.captured:
            return attackers_success
        else:
            return not attackers_success

    def commit(self, debriefing: Debriefing):
        super(CaptureEvent, self).commit(debriefing)
        if self.is_successfull(debriefing):
            if self.from_cp.captured:
                self.to_cp.captured = True
                self.to_cp.base.filter_units(db.UNIT_BY_COUNTRY[self.attacker_name])

            self.to_cp.base.affect_strength(+self.STRENGTH_RECOVERY)
        else:
            if not self.from_cp.captured:
                self.to_cp.captured = False
            self.to_cp.base.affect_strength(+self.STRENGTH_RECOVERY)

    def skip(self):
        if self.to_cp.captured:
            self.to_cp.captured = False

    def player_defending(self, interceptors: db.PlaneDict, clients: db.PlaneDict):
        cas = self.from_cp.base.scramble_cas()
        escort = self.from_cp.base.scramble_sweep()
        attackers = self.from_cp.base.assemble_cap()

        op = CaptureOperation(game=self.game,
                              attacker_name=self.attacker_name,
                              defender_name=self.defender_name,
                              attacker_clients={},
                              defender_clients=clients,
                              from_cp=self.from_cp,
                              to_cp=self.to_cp)

        op.setup(cas=cas,
                 escort=escort,
                 attack=attackers,
                 intercept=interceptors,
                 defense=self.to_cp.base.armor,
                 aa=self.to_cp.base.aa)

        self.operation = op

    def player_attacking(self, cas: db.PlaneDict, escort: db.PlaneDict, armor: db.ArmorDict, clients: db.PlaneDict):
        interceptors = self.to_cp.base.scramble_sweep()

        op = CaptureOperation(game=self.game,
                              attacker_name=self.attacker_name,
                              defender_name=self.defender_name,
                              attacker_clients=clients,
                              defender_clients={},
                              from_cp=self.from_cp,
                              to_cp=self.to_cp)

        op.setup(cas=cas,
                 escort=escort,
                 attack=armor,
                 intercept=interceptors,
                 defense=self.to_cp.base.armor,
                 aa=self.to_cp.base.assemble_aa())

        self.operation = op


class UnitsDeliveryEvent(Event):
    informational = True
    units = None  # type: typing.Dict[UnitType, int]

    def __init__(self, attacker_name: str, defender_name: str, from_cp: ControlPoint, to_cp: ControlPoint, game):
        super(UnitsDeliveryEvent, self).__init__(attacker_name=attacker_name,
                                                 defender_name=defender_name,
                                                 from_cp=from_cp,
                                                 to_cp=to_cp,
                                                 game=game)

        self.units = {}

    def __str__(self):
        return "Pending delivery to {}".format(self.to_cp)

    def deliver(self, units: typing.Dict[UnitType, int]):
        for k, v in units.items():
            self.units[k] = self.units.get(k, 0) + v

    def skip(self):
        self.to_cp.base.commision_units(self.units)