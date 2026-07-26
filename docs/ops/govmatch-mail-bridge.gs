// govmatch-mail-bridge.gs — 대표 구글계정에 설치. 인프라 알림을 지원금AI 백엔드로 전송.
//
// [설치]
// 1) script.google.com → 새 프로젝트 → 이 코드 전체 붙여넣기
// 2) 프로젝트 설정(⚙) → 스크립트 속성 추가:
//      BACKEND_URL  = https://govmatch-production.up.railway.app/api/internal/mail-signal
//      BRIDGE_SECRET = (Railway env MAIL_BRIDGE_SECRET 와 동일한 값)
// 3) 트리거(⏰) → scanInfraAlerts 추가 → 시간 기반 → 일 단위 타이머 → 오전 8~9시
//    (AI COO 09:30 보고 직전이라 당일 신호가 반영됨)
// 4) 최초 실행 시 Gmail 접근 권한 승인 요청 → 허용
//
// 읽기 전용: 메일 수정·발송·삭제 없음. 처리한 스레드에 'govmatch-processed' 라벨만 부착.
var LABEL = 'govmatch-processed';
var SENDERS = 'from:(railway.app OR vercel.com OR supabase.io OR supabase.com)';

function scanInfraAlerts() {
  var props = PropertiesService.getScriptProperties();
  var url = props.getProperty('BACKEND_URL');
  var secret = props.getProperty('BRIDGE_SECRET');
  if (!url || !secret) {
    Logger.log('BACKEND_URL / BRIDGE_SECRET 스크립트 속성 미설정 — 중단');
    return;
  }
  var label = GmailApp.getUserLabelByName(LABEL) || GmailApp.createLabel(LABEL);
  var threads = GmailApp.search(SENDERS + ' newer_than:1d -label:' + LABEL, 0, 20);
  threads.forEach(function (th) {
    var msgs = th.getMessages();
    var allOk = true;
    msgs.forEach(function (m) {
      var payload = {
        msg_id: m.getId(),
        date: m.getDate().toISOString(),
        from: m.getFrom(),
        subject: m.getSubject(),
        snippet: m.getPlainBody().slice(0, 300),
      };
      if (!postWithRetry(url, secret, payload)) allOk = false;
    });
    if (allOk) th.addLabel(label); // 전송 성공한 스레드만 처리표시 → 실패분은 다음날 재시도
  });
}

function postWithRetry(url, secret, payload) {
  for (var i = 0; i < 3; i++) { // 동일 실행 내 2~3회 재시도(일시 실패 흡수 — 하루 1회라 24h 지연 방지)
    try {
      var res = UrlFetchApp.fetch(url, {
        method: 'post',
        contentType: 'application/json',
        headers: { 'X-Bridge-Secret': secret },
        payload: JSON.stringify(payload),
        muteHttpExceptions: true,
      });
      var code = res.getResponseCode();
      if (code >= 200 && code < 300) return true;
    } catch (e) {}
    Utilities.sleep(1500);
  }
  return false;
}
