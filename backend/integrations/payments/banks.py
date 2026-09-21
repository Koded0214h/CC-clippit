"""Nigerian banks by CBN code. Used by the sandbox provider; a real provider
returns its own list (the codes are the same industry codes, so a creator's
saved `bank_code` survives a provider switch)."""

from .base import Bank

NIGERIAN_BANKS: tuple[Bank, ...] = (
    Bank("044", "Access Bank"),
    Bank("063", "Access Bank (Diamond)"),
    Bank("035", "Wema Bank"),
    Bank("050", "Ecobank Nigeria"),
    Bank("070", "Fidelity Bank"),
    Bank("011", "First Bank of Nigeria"),
    Bank("214", "First City Monument Bank"),
    Bank("058", "Guaranty Trust Bank"),
    Bank("030", "Heritage Bank"),
    Bank("301", "Jaiz Bank"),
    Bank("082", "Keystone Bank"),
    Bank("076", "Polaris Bank"),
    Bank("101", "Providus Bank"),
    Bank("221", "Stanbic IBTC Bank"),
    Bank("068", "Standard Chartered Bank"),
    Bank("232", "Sterling Bank"),
    Bank("100", "Suntrust Bank"),
    Bank("032", "Union Bank of Nigeria"),
    Bank("033", "United Bank for Africa"),
    Bank("215", "Unity Bank"),
    Bank("057", "Zenith Bank"),
    Bank("50211", "Kuda Microfinance Bank"),
    Bank("50515", "Moniepoint Microfinance Bank"),
    Bank("999991", "PalmPay"),
    Bank("999992", "OPay"),
)

BANKS_BY_CODE = {bank.code: bank for bank in NIGERIAN_BANKS}
