"""API response fixtures for KIS Client tests.

These fixtures mimic the structure of actual KIS API responses.
"""

# OAuth Token Response (success)
KIS_TOKEN_RESPONSE_SUCCESS = {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.mock_token",
    "token_type": "Bearer",
    "expires_in": 86400,  # 24 hours
    "access_token_token_expired": "2025-01-02 12:00:00",
}

# OAuth Token Response (error)
KIS_TOKEN_RESPONSE_ERROR = {
    "error": "invalid_client",
    "error_description": "Invalid client credentials",
}

# Domestic Stock Quote Response (Samsung 005930)
KIS_DOMESTIC_QUOTE_RESPONSE = {
    "rt_cd": "0",
    "msg_cd": "MCA00000",
    "msg1": "정상처리 되었습니다.",
    "output": {
        "iscd_stat_cls_code": "55",
        "marg_rate": "20.00",
        "rprs_mrkt_kor_name": "코스피",
        "bstp_kor_isnm": "전기전자",
        "temp_stop_yn": "N",
        "oprc_rang_cont_yn": "N",
        "clpr_rang_cont_yn": "N",
        "crdt_able_yn": "Y",
        "stck_prpr": "78500",  # 현재가
        "prdy_vrss": "500",  # 전일대비
        "prdy_vrss_sign": "2",
        "prdy_ctrt": "0.64",  # 등락률
        "acml_vol": "12345678",  # 누적거래량
        "acml_tr_pbmn": "968574213500",
        "stck_dryy_hgpr": "85000",  # 52주 최고가
        "stck_dryy_lwpr": "65000",  # 52주 최저가
        "hts_avls": "4685000",  # 시가총액(억)
        "per": "12.34",
        "pbr": "1.45",
        "eps": "6361",
        "bps": "54138",
    },
}

# Domestic Stock Quote Response (minimal data)
KIS_DOMESTIC_QUOTE_RESPONSE_MINIMAL = {
    "rt_cd": "0",
    "msg_cd": "MCA00000",
    "msg1": "정상처리 되었습니다.",
    "output": {
        "stck_prpr": "50000",
        "prdy_vrss": "-1000",
        "prdy_ctrt": "-1.96",
        "acml_vol": "1000000",
        # Other fields missing or empty
        "stck_dryy_hgpr": "",
        "stck_dryy_lwpr": "",
        "hts_avls": "",
        "per": "-",
        "pbr": "0",
        "eps": "",
        "bps": "",
    },
}

# Domestic Stock Quote Response (error - invalid ticker)
KIS_DOMESTIC_QUOTE_RESPONSE_ERROR = {
    "rt_cd": "1",
    "msg_cd": "EGW00123",
    "msg1": "유효하지 않은 종목코드입니다.",
    "output": {},
}

# Foreign Stock Quote Response (Apple AAPL)
KIS_FOREIGN_QUOTE_RESPONSE = {
    "rt_cd": "0",
    "msg_cd": "MCA00000",
    "msg1": "정상처리 되었습니다.",
    "output": {
        "rsym": "AAPL",
        "excd": "NAS",
        "symb": "AAPL",
        "name": "APPLE INC",
        "last": "195.25",  # 현재가
        "diff": "2.50",  # 전일대비
        "rate": "1.30",  # 등락률
        "tvol": "52345678",  # 거래량
        "h52p": "199.62",  # 52주 최고가
        "l52p": "164.08",  # 52주 최저가
        "perx": "30.15",  # PER
        "pbrx": "45.20",  # PBR
        "epsx": "6.48",  # EPS
        "bpsx": "4.32",  # BPS
    },
}

# Foreign Stock Quote Response (minimal data)
KIS_FOREIGN_QUOTE_RESPONSE_MINIMAL = {
    "rt_cd": "0",
    "msg_cd": "MCA00000",
    "msg1": "정상처리 되었습니다.",
    "output": {
        "rsym": "TEST",
        "excd": "NYS",
        "symb": "TEST",
        "last": "50.00",
        "diff": "-0.50",
        "rate": "-0.99",
        "tvol": "100000",
        # Other fields empty
        "h52p": "",
        "l52p": "",
        "perx": "-",
        "pbrx": "0",
        "epsx": "",
        "bpsx": "",
    },
}

# Rate Limit Response
KIS_RATE_LIMIT_RESPONSE = {
    "rt_cd": "1",
    "msg_cd": "EGW00201",
    "msg1": "초당 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요.",
}
