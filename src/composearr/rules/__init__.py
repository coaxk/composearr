"""Rule registry — import all rule modules to trigger registration."""

# Import rule modules so __init_subclass__ registers them
from composearr.rules import CA0xx_images  # noqa: F401
from composearr.rules import CA0xx_registries  # noqa: F401
from composearr.rules import CA1xx_security  # noqa: F401
from composearr.rules import CA2xx_reliability  # noqa: F401
from composearr.rules import CA3xx_networking  # noqa: F401
from composearr.rules import CA3xx_network_topology  # noqa: F401
from composearr.rules import CA4xx_consistency  # noqa: F401
from composearr.rules import CA5xx_resources  # noqa: F401
from composearr.rules import CA6xx_arrstack  # noqa: F401
from composearr.rules import CA7xx_volumes  # noqa: F401
from composearr.rules import CA8xx_security  # noqa: F401
from composearr.rules import CA9xx_advanced  # noqa: F401
from composearr.rules.base import get_all_rules, get_rule  # noqa: F401
