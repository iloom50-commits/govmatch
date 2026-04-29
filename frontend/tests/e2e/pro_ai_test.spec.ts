import { test, expect } from '@playwright/test';

const API = 'https://govmatch-production.up.railway.app';
const HEADERS = { 'Content-Type': 'application/json' };

async function getToken(request: any): Promise<string> {
  const res = await request.post(`${API}/api/auth/login`, {
    headers: HEADERS,
    data: { email: 'pro_test@test.com', password: 'Test1234!' },
  });
  const d = await res.json();
  if (!d.token) throw new Error(`로그인 실패: ${JSON.stringify(d)}`);
  console.log(`✅ 로그인 완료 (plan: ${d.plan?.plan})`);
  return d.token;
}

function auth(token: string) {
  return { ...HEADERS, Authorization: `Bearer ${token}` };
}

// 테스트용 기업 프로필 (profile_override로 매칭 엔진에 직접 주입)
const TEST_PROFILE = {
  company_name: 'AI테스트기업',
  industry_name: '소프트웨어 개발',
  industry_code: '62010',
  employee_count: 8,
  revenue: 500000000,
  establishment_date: '2022-01-01',
  address_city: '서울',
  user_type: 'business',
  interests: '기술개발,창업지원,디지털전환',
};

// ══════════════════════════════════════════════════════════════
// TEST 1: PRO 매칭 AI
// ══════════════════════════════════════════════════════════════
test('TEST1 PRO 매칭 AI — IT 스타트업 R&D 자금 매칭', async ({ request }) => {
  const token = await getToken(request);
  const sid = `test-match-${Date.now()}`;

  const res = await request.post(`${API}/api/pro/consultant/chat`, {
    headers: auth(token),
    data: {
      action: 'match',
      session_id: sid,
      profile_override: TEST_PROFILE,
      messages: [{ role: 'user', text: 'IT 스타트업 직원 8명, 서울 소재입니다. AI 기술개발 R&D 자금이 필요합니다. 맞는 지원사업 찾아주세요.' }],
    },
  });

  const d = await res.json();
  const reply = d.reply || d.message || '';
  const matched = d.matched_announcements || [];

  console.log(`\n[매칭 응답 (${reply.length}자)]:\n${reply.slice(0, 400)}`);
  console.log(`[매칭 공고 수]: ${matched.length}개`);
  if (matched.length > 0)
    console.log(`[상위 3개]: ${matched.slice(0, 3).map((m: any) => m.title?.slice(0, 30)).join(' / ')}`);
  if (d.outer_error) console.error(`[outer_error]: ${d.outer_error}`);

  expect(reply.length, '매칭 응답이 너무 짧음').toBeGreaterThan(50);
  expect(/지원|사업|공고|매칭|자금|기술|창업/i.test(reply), '관련 키워드 없음').toBeTruthy();

  // 후속: 서울 필터
  const res2 = await request.post(`${API}/api/pro/consultant/chat`, {
    headers: auth(token),
    data: {
      action: 'match',
      session_id: sid,
      profile_override: { ...TEST_PROFILE, address_city: '서울' },
      messages: [
        { role: 'user', text: 'IT 스타트업 R&D 자금 필요' },
        { role: 'assistant', text: reply },
        { role: 'user', text: '서울 지역 한정으로 다시 찾아줘' },
      ],
    },
  });
  const d2 = await res2.json();
  const reply2 = d2.reply || d2.message || '';
  console.log(`\n[지역필터 응답 (${reply2.length}자)]:\n${reply2.slice(0, 200)}`);
  expect(reply2.length, '지역필터 응답 없음').toBeGreaterThan(20);

  console.log('✅ TEST1 통과');
});

// ══════════════════════════════════════════════════════════════
// TEST 2: PRO 공고 상담 AI
// ══════════════════════════════════════════════════════════════
test('TEST2 PRO 공고 상담 AI — 자격요건 + 전략 분석', async ({ request }) => {
  const token = await getToken(request);

  // 공고 목록 조회
  const listRes = await request.get(`${API}/api/announcements/search?limit=5`, { headers: auth(token) });
  const listData = await listRes.json();
  const items = listData.data || listData.announcements || listData.items || [];

  if (items.length === 0) {
    console.warn('⚠️ 공고 없음 — 스킵');
    return;
  }

  const target = items[0];
  const aid = target.id || target.announcement_id;
  console.log(`\n[대상 공고] id=${aid} | ${(target.title || '').slice(0, 50)}`);

  const sid = `test-consult-${Date.now()}`;
  const res = await request.post(`${API}/api/pro/consultant/chat`, {
    headers: auth(token),
    data: {
      action: 'consult',
      session_id: sid,
      announcement_id: aid,
      messages: [{ role: 'user', text: '이 공고에 대해 자격요건과 신청 전략을 자세히 알려줘' }],
    },
  });

  const d = await res.json();
  const reply = d.reply || d.message || '';
  const insights = d.expert_insights;

  console.log(`\n[공고상담 응답 (${reply.length}자)]:\n${reply.slice(0, 500)}`);
  console.log(`[expert_insights]: ${!!insights} ${insights ? '| 필드: ' + Object.keys(insights).join(', ') : ''}`);
  if (d.outer_error) console.error(`[outer_error]: ${d.outer_error}`);

  expect(reply.length, '공고 상담 응답 없음').toBeGreaterThan(100);
  expect(/지원|자격|요건|신청|대상|사업/i.test(reply), '공고 관련 키워드 없음').toBeTruthy();

  // 후속 질문
  const res2 = await request.post(`${API}/api/pro/consultant/chat`, {
    headers: auth(token),
    data: {
      action: 'consult',
      session_id: sid,
      announcement_id: aid,
      messages: [
        { role: 'user', text: '자격요건 알려줘' },
        { role: 'assistant', text: reply },
        { role: 'user', text: '창업 2년차 소기업도 신청 가능한가요?' },
      ],
    },
  });
  const d2 = await res2.json();
  const reply2 = d2.reply || d2.message || '';
  console.log(`\n[후속 응답 (${reply2.length}자)]:\n${reply2.slice(0, 300)}`);
  expect(reply2.length, '후속 응답 없음').toBeGreaterThan(30);

  console.log('✅ TEST2 통과');
});

// ══════════════════════════════════════════════════════════════
// TEST 3: 매칭 후 chat 모드 전환
// ══════════════════════════════════════════════════════════════
test('TEST3 매칭 후 chat 모드 — 매칭엔진 재실행 없이 대화', async ({ request }) => {
  const token = await getToken(request);
  const sid = `test-chatmode-${Date.now()}`;

  // 1단계: 매칭
  const matchRes = await request.post(`${API}/api/pro/consultant/chat`, {
    headers: auth(token),
    data: {
      action: 'match',
      session_id: sid,
      profile_override: { ...TEST_PROFILE, industry_name: '제조업', address_city: '경기도' },
      messages: [{ role: 'user', text: '제조업 소기업, 경기도 소재입니다. 설비투자 지원사업 찾아주세요.' }],
    },
  });
  const matchData = await matchRes.json();
  const matchReply = matchData.reply || matchData.message || '';
  console.log(`\n[매칭 응답 (${matchReply.length}자)]:\n${matchReply.slice(0, 300)}`);
  expect(matchReply.length, '매칭 응답 없음').toBeGreaterThan(20);

  // 2단계: chat 모드
  const chatRes = await request.post(`${API}/api/pro/consultant/chat`, {
    headers: auth(token),
    data: {
      action: 'chat',
      session_id: sid,
      messages: [
        { role: 'user', text: '제조업 소기업, 경기도, 설비투자 지원 필요' },
        { role: 'assistant', text: matchReply },
        { role: 'user', text: '이 중에서 신청서류가 가장 간단한 것은?' },
      ],
    },
  });
  const chatData = await chatRes.json();
  const chatReply = chatData.reply || chatData.message || '';
  const newMatched = chatData.matched_announcements || [];

  console.log(`\n[chat 응답 (${chatReply.length}자)]:\n${chatReply.slice(0, 300)}`);
  console.log(`[매칭엔진 재실행]: ${newMatched.length > 0 ? '⚠️ 재실행됨' : '✅ 정상'}`);
  if (chatData.outer_error) console.error(`[outer_error]: ${chatData.outer_error}`);

  expect(chatReply.length, 'chat 응답 없음').toBeGreaterThan(30);
  expect(newMatched.length, 'chat 모드에서 매칭엔진 재실행됨').toBe(0);

  console.log('✅ TEST3 통과');
});

// ══════════════════════════════════════════════════════════════
// TEST 4: LITE 자금상담 AI
// ══════════════════════════════════════════════════════════════
test('TEST4 LITE 자금상담 AI — 청년 창업 개인 자금 상담', async ({ request }) => {
  const token = await getToken(request);
  const sid = `test-fund-${Date.now()}`;

  const res = await request.post(`${API}/api/ai/chat`, {
    headers: auth(token),
    data: {
      mode: 'individual_fund',
      session_id: sid,
      messages: [{ role: 'user', text: '저는 만 28세 청년이고 AI 스타트업 창업을 준비 중입니다. 받을 수 있는 정부 창업자금이 뭐가 있나요?' }],
    },
  });

  const d = await res.json();
  const reply = d.reply || d.message || d.answer || d.response || '';
  console.log(`\n[자금상담 응답 (${reply.length}자)]:\n${reply.slice(0, 500)}`);
  if (d.outer_error) console.error(`[outer_error]: ${d.outer_error}`);

  expect(reply.length, '자금상담 응답 없음').toBeGreaterThan(100);
  expect(/청년|창업|지원|자금|융자|대출|보조|정책/i.test(reply), '자금 관련 키워드 없음').toBeTruthy();

  // 후속 질문
  const res2 = await request.post(`${API}/api/ai/chat`, {
    headers: auth(token),
    data: {
      mode: 'individual_fund',
      session_id: sid,
      messages: [
        { role: 'user', text: '만 28세 AI 스타트업 창업 준비 중' },
        { role: 'assistant', text: reply },
        { role: 'user', text: '담보 없이 받을 수 있는 것만 알려줘' },
      ],
    },
  });
  const d2 = await res2.json();
  const reply2 = d2.reply || d2.message || d2.answer || d2.response || '';
  console.log(`\n[후속 응답 (${reply2.length}자)]:\n${reply2.slice(0, 300)}`);
  expect(reply2.length, '후속 응답 없음').toBeGreaterThan(30);

  console.log('✅ TEST4 통과');
});
