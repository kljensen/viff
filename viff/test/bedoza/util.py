
from viff.test.util import RuntimeTestCase
from viff.config import generate_configs

from viff.bedoza.bedoza import BeDOZaRuntime

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

    runtime_class = BeDOZaRuntime

    def setUp(self):
        RuntimeTestCase.setUp(self)
        self.security_parameter = 32

    # TODO: During test, we would like generation of Paillier keys to
    # be deterministic. How do we obtain that?
    def generate_configs(self, *args):
        # In production, paillier keys should be something like 2000
        # bit. For test purposes, it is ok to use small keys.
        # TODO: paillier freezes if key size is too small, e.g. 13.
        return generate_configs(paillier=NaClPaillier(250), *args)


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
