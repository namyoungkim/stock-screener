"""HTML fixtures for Naver Finance tests.

These fixtures mimic the structure of actual Naver Finance pages.
"""

# Main page (item/main.naver) - contains PER, EPS, PBR, BPS
NAVER_MAIN_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head><title>삼성전자 - 네이버 금융</title></head>
<body>
<div class="new_totalinfo">
    <div class="section">
        <table class="per_table">
            <tr>
                <th>PER</th>
                <td><em id="_per">12.34</em>배</td>
                <td>l</td>
                <th>EPS</th>
                <td><em id="_eps">6,789</em>원</td>
            </tr>
            <tr>
                <th>추정PER</th>
                <td>11.50배</td>
                <td>l</td>
                <th>추정EPS</th>
                <td>7,200원</td>
            </tr>
            <tr>
                <th>PBR</th>
                <td><em id="_pbr">1.45</em>배</td>
                <td>l</td>
                <th>BPS</th>
                <td>1.45배 l 55,000원</td>
            </tr>
        </table>
    </div>
</div>
</body>
</html>
"""

# Main page with missing values (dash for unavailable data)
NAVER_MAIN_PAGE_HTML_MISSING = """
<!DOCTYPE html>
<html>
<head><title>테스트 종목 - 네이버 금융</title></head>
<body>
<div class="new_totalinfo">
    <div class="section">
        <table class="per_table">
            <tr>
                <th>PER</th>
                <td><em id="_per">-</em>배</td>
                <td>l</td>
                <th>EPS</th>
                <td><em id="_eps">-</em>원</td>
            </tr>
            <tr>
                <th>PBR</th>
                <td><em id="_pbr">0.85</em>배</td>
                <td>l</td>
                <th>BPS</th>
                <td>0.85배 l 12,000원</td>
            </tr>
        </table>
    </div>
</div>
</body>
</html>
"""

# Empty/invalid page
NAVER_MAIN_PAGE_HTML_EMPTY = """
<!DOCTYPE html>
<html>
<head><title>페이지를 찾을 수 없습니다</title></head>
<body>
<div class="error">요청하신 페이지를 찾을 수 없습니다.</div>
</body>
</html>
"""

# Financial ratios page (item/coinfo.naver?target=finsum_more)
NAVER_COINFO_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head><title>삼성전자 기업개요 - 네이버 금융</title></head>
<body>
<div class="section">
    <table class="tb_type1">
        <caption>투자지표</caption>
        <tbody>
            <tr>
                <th>ROE(%)</th>
                <td>15.32</td>
            </tr>
            <tr>
                <th>ROA(%)</th>
                <td>8.75</td>
            </tr>
            <tr>
                <th>부채비율</th>
                <td>35.50%</td>
            </tr>
            <tr>
                <th>유동비율</th>
                <td>245.80%</td>
            </tr>
        </tbody>
    </table>
</div>
</body>
</html>
"""

# Financial ratios page with partial data
NAVER_COINFO_PAGE_HTML_PARTIAL = """
<!DOCTYPE html>
<html>
<head><title>테스트 종목 기업개요</title></head>
<body>
<div class="section">
    <table class="tb_type1">
        <tbody>
            <tr>
                <th>ROE(%)</th>
                <td>22.50</td>
            </tr>
            <tr>
                <th>부채비율</th>
                <td>120.30%</td>
            </tr>
        </tbody>
    </table>
</div>
</body>
</html>
"""

# Sise page (item/sise.naver) - contains market cap, dividend yield
NAVER_SISE_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head><title>삼성전자 시세 - 네이버 금융</title></head>
<body>
<div class="section">
    <table class="tb_type1">
        <tbody>
            <tr>
                <th>시가총액</th>
                <td>4,500,000억원</td>
            </tr>
            <tr>
                <th>시가총액순위</th>
                <td>코스피 1위</td>
            </tr>
            <tr>
                <th>배당수익률</th>
                <td>2.35%</td>
            </tr>
            <tr>
                <th>외국인소진율</th>
                <td>52.30%</td>
            </tr>
        </tbody>
    </table>
</div>
</body>
</html>
"""

# Sise page with smaller market cap (no 조)
NAVER_SISE_PAGE_HTML_SMALL_CAP = """
<!DOCTYPE html>
<html>
<head><title>테스트 종목 시세</title></head>
<body>
<div class="section">
    <table class="tb_type1">
        <tbody>
            <tr>
                <th>시가총액</th>
                <td>1,234억원</td>
            </tr>
            <tr>
                <th>배당수익률</th>
                <td>0.50%</td>
            </tr>
        </tbody>
    </table>
</div>
</body>
</html>
"""

# Sise page with no dividend
NAVER_SISE_PAGE_HTML_NO_DIVIDEND = """
<!DOCTYPE html>
<html>
<head><title>테스트 종목 시세</title></head>
<body>
<div class="section">
    <table class="tb_type1">
        <tbody>
            <tr>
                <th>시가총액</th>
                <td>500억원</td>
            </tr>
            <tr>
                <th>배당수익률</th>
                <td>-</td>
            </tr>
        </tbody>
    </table>
</div>
</body>
</html>
"""
