
from viff.config import generate_configs

from viff.test.util import RuntimeTestCase

from viff.bedoza.bedoza import BeDOZaRuntime
from viff.bedoza.util import _convolute
from viff.bedoza.add_macs import add_macs
from viff.bedoza.shares import PartialShare, PartialShareContents


# HACK: The paillier keys that are available as standard in VIFF tests
# are not suited for use with pypaillier. Hence, we use NaClPaillier
# to generate test keys. This confusion will disappear when pypaillier
# replaces the current Python-based paillier implementation.
from viff.paillierutil import NaClPaillier

# HACK^2: Currently, the NaClPaillier hack only works when triple is
# imported. It should ideally work without the triple package.
try:
    import tripple
except ImportError:
    tripple = None

# The PyPaillier and commitment packages are not standard parts of VIFF so we
# skip them instead of letting them fail if the packages are not available. 
try:
    import pypaillier
except ImportError:
    pypaillier = None



def log(rt, msg):
    print "player%d ------> %s" % (rt.id, msg)


class BeDOZaTestCase(RuntimeTestCase):

    num_players = 3

    runtime_class = BeDOZaRuntime

    # In production, paillier keys should be something like 2000
    # bit. For test purposes, it is ok to use small keys.
    # TODO: paillier freezes if key size is too small, e.g. 13.
    paillier_key_size = 250

    def setUp(self):
        RuntimeTestCase.setUp(self)
        self.security_parameter = 32

    # TODO: During test, we would like generation of Paillier keys to
    # be deterministic. How do we obtain that?
    def generate_configs(self, *args):
        return generate_configs(
            paillier=NaClPaillier(self.paillier_key_size), *args)


def skip_if_missing_packages(*test_cases):
    """Skipts the given list of test cases if some of the required
    external viff packages (tripple, pypaillier) is not available.
    """
    missing = []
    if not pypaillier:
        missing.append("pypaillier")
    if not tripple:
        missing.append("tripple")
    if missing:
        for test_case in test_cases:
            test_case.skip =  "Skipped due to missing packages: %s" % missing


class TestPartialShareGenerator(object):
    """Class for quick generation of partial shares with no
    security. Suited only for use when partial shares are needed as
    input to a test.
    """

    def __init__(self, Zp, runtime, random, paillier):
        self.paillier = paillier
        self.Zp = Zp
        self.runtime = runtime
        self.random = random

    def generate_share(self, value):
        self.runtime.increment_pc()
        
        # TODO: Exclusive?
        r = [self.Zp(self.random.randint(0, self.Zp.modulus - 1))
             for _ in range(self.runtime.num_players - 1)]
        if self.runtime.id == 1:
            share = value - sum(r)
        else:
            share = r[self.runtime.id - 2]
        enc_share = self.paillier.encrypt(share.value)
        enc_shares = _convolute(self.runtime, enc_share)
        def create_partial_share(enc_shares, share):
            return PartialShare(self.runtime, self.Zp, share, enc_shares)
        self.runtime.schedule_callback(enc_shares, create_partial_share, share)
        return enc_shares

    def generate_random_shares(self, n):
        self.runtime.increment_pc()
        N_squared_list = [self.runtime.players[player_id].pubkey['n_square']
                          for player_id in self.runtime.players]
        shares = [PartialShare(self.runtime, self.Zp) for _ in xrange(n)]
        for inx in xrange(n):
            r = self.random.randint(0, self.Zp.modulus - 1)
            ri = self.Zp(r)
            enc_share = self.paillier.encrypt(ri.value)
            enc_shares = _convolute(self.runtime, enc_share)
            def create_partial_share(enc_shares, ri, s, N_squared_list):
                s.callback(PartialShareContents(ri, enc_shares,
                                                N_squared_list))
            self.runtime.schedule_callback(enc_shares,
                                           create_partial_share,
                                           ri,
                                           shares[inx],
                                           N_squared_list)
        return shares

class TestShareGenerator(TestPartialShareGenerator):
    """Class for quick generation of shares with no security. Suited
    only for use when shares are needed as input to a test.
    """

    def __init__(self, Zp, runtime, random, paillier, u_bound, alpha):
        self.u_bound = u_bound
        self.alpha = alpha
        TestPartialShareGenerator.__init__(self, Zp, runtime, random, paillier)

    def generate_share(self, value):
        self.runtime.increment_pc()
        partial_share = TestPartialShareGenerator.generate_share(self, value)
        full_share = add_macs(self.runtime, self.Zp, self.u_bound, self.alpha,
                             self.random, self.paillier, [partial_share])
        return full_share[0]
    
    def generate_random_shares(self, n):
        self.runtime.increment_pc()
        partial_shares = TestPartialShareGenerator.generate_random_shares(self, n)
        return add_macs(self.runtime, self.Zp, self.u_bound, self.alpha,
                        self.random, self.paillier, partial_shares)
