from dataclasses import dataclass, field


@dataclass
class ExecutionContext:
    """
    Stores shared state during plan execution.

    The context allows execution steps to exchange
    intermediate data without directly depending
    on one another.
    """

    variables: dict = field(
        default_factory=dict
    )

    results: dict = field(
        default_factory=dict
    )

    metadata: dict = field(
        default_factory=dict
    )