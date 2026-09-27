// 视频管家 cookie 助手：抖音页面加载完成后，把该域的全部 cookie（含
// httpOnly——这是绕开浏览器加密与文件锁的关键）上报给本机的视频管家。
// 上报地址只走 127.0.0.1，不出本机。

const SYNC_URL = "http://127.0.0.1:18642/cookies";
// 页面加载完成后等几秒：ttwid 等 cookie 由页面 JS/响应头稍后才种上
const REPORT_DELAY_MS = 5000;

async function reportCookies() {
  try {
    const cookies = await chrome.cookies.getAll({ domain: "douyin.com" });
    if (!cookies.length) return;
    await fetch(SYNC_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cookies.map(c => ({
        domain: c.domain,
        path: c.path,
        secure: c.secure,
        expirationDate: c.expirationDate,
        name: c.name,
        value: c.value,
      }))),
    });
    console.log("[视频管家] 已同步", cookies.length, "条 cookie");
  } catch (e) {
    // 视频管家没开着（连不上）属正常场景，静默即可
    console.log("[视频管家] 同步跳过:", e.message);
  }
}

chrome.tabs.onUpdated.addListener((tabId, info, tab) => {
  if (info.status === "complete" && tab.url && tab.url.includes("douyin.com")) {
    setTimeout(reportCookies, REPORT_DELAY_MS);
  }
});

// 已有抖音标签页时立即上报：覆盖两类竞态——SW 冷启动晚于页面加载
// （complete 事件发在监听器注册之前而丢失）、扩展装到已开着抖音的浏览器
async function reportIfDouyinOpen() {
  try {
    const tabs = await chrome.tabs.query({ url: "*://*.douyin.com/*" });
    if (tabs.length) setTimeout(reportCookies, REPORT_DELAY_MS);
  } catch (e) { /* tabs 权限异常时静默：onUpdated 仍会兜底 */ }
}
chrome.runtime.onInstalled.addListener(reportIfDouyinOpen);
// SW 每次被唤醒都扫一遍（顶层执行，任何事件唤醒都会跑）
reportIfDouyinOpen();

// 扩展图标点一下也立即同步（手动兜底入口）
chrome.action && chrome.action.onClicked && chrome.action.onClicked.addListener(reportCookies);
