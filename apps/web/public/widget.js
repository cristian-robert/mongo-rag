"use strict";(()=>{var z={system:{label:"System",stack:'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',google:null,role:"body"},inter:{label:"Inter",stack:'Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',google:"Inter:wght@400;500;600",role:"body"},geist:{label:"Geist",stack:'Geist, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',google:"Geist:wght@400;500;600",role:"body"},"ibm-plex-sans":{label:"IBM Plex Sans",stack:'"IBM Plex Sans", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',google:"IBM+Plex+Sans:wght@400;500;600",role:"body"},"work-sans":{label:"Work Sans",stack:'"Work Sans", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',google:"Work+Sans:wght@400;500;600",role:"body"},fraunces:{label:"Fraunces",stack:'Fraunces, ui-serif, "Iowan Old Style", "Times New Roman", Georgia, serif',google:"Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600",role:"display"},"jetbrains-mono":{label:"JetBrains Mono",stack:'"JetBrains Mono", ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',google:"JetBrains+Mono:wght@400;500;600",role:"mono"}},D=Object.keys(z);function $(e){return z[e].stack}function re(e){let t=new Set;for(let n of e){let a=z[n]?.google;a&&t.add(a)}return t.size===0?null:`https://fonts.googleapis.com/css2?${Array.from(t).map(n=>`family=${n}`).join("&")}&display=swap`}function ne(){if(typeof window>"u"||typeof window.matchMedia!="function")return!1;try{return window.matchMedia("(prefers-reduced-data: reduce)").matches}catch{return!1}}var Re="https://api.mongorag.com",Pe="#0f172a",ae=/^(#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?|rgb\([\d,\s]+\)|rgba\([\d,.\s]+\))$/,Fe=new Set(["bottom-right","bottom-left"]),Le=new Set(["light","dark","auto"]),Oe=new Set(["none","sm","md","lg","full"]),We=new Set(["compact","comfortable","spacious"]),Ne=new Set(["sm","md","lg"]),Ue=new Set(["circle","rounded-square","pill"]),ze=new Set(["chat","sparkle","book","question","custom"]),oe=/[\x00-\x1F\x7F]/g,x=class extends Error{constructor(t){super(t),this.name="ConfigError"}};function ie(e){let t=e.dataset,r={apiKey:t.apiKey,apiUrl:t.apiUrl,botId:t.botId,primaryColor:t.primaryColor,botName:t.botName,welcomeMessage:t.welcomeMessage,position:t.position};return t.showBranding!==void 0&&(r.showBranding=t.showBranding),r}function se(e,t){return{...t??{},...e??{}}}function De(e){let t;try{t=new URL(e)}catch{throw new x(`apiUrl is not a valid URL: ${e}`)}if(t.protocol!=="http:"&&t.protocol!=="https:")throw new x(`apiUrl must be http or https: ${e}`);return e.replace(/\/+$/,"")}function L(e,t){return!e||!ae.test(e)?t:e}function g(e){return!e||!ae.test(e)?null:e}function O(e,t="bottom-right"){return e&&Fe.has(e)?e:t}function B(e,t="light"){return e&&Le.has(e)?e:t}function H(e,t="system"){return e&&D.includes(e)?e:t}function K(e){return!e||!D.includes(e)?null:e}function G(e,t="md"){return e&&Oe.has(e)?e:t}function j(e,t="comfortable"){return e&&We.has(e)?e:t}function k(e,t="md"){return e&&Ne.has(e)?e:t}function q(e,t="circle"){return e&&Ue.has(e)?e:t}function Y(e,t="chat"){return e&&ze.has(e)?e:t}function w(e,t,r=200){return e&&e.replace(oe,"").slice(0,r)||t}function J(e,t=80){return e&&e.replace(oe,"").slice(0,t).trim()||null}function A(e){if(!e)return null;let t=e.trim();if(t.length===0||t.length>500||!t.startsWith("https://"))return null;try{return new URL(t).protocol==="https:"?t:null}catch{return null}}function $e(e,t){if(typeof e=="boolean")return e;if(typeof e=="string"){if(e==="true")return!0;if(e==="false")return!1}return t}function le(e){let t=(e.apiKey??"").trim();if(!t)throw new x("Missing required apiKey (data-api-key)");if(!t.startsWith("mrag_"))throw new x("apiKey must start with 'mrag_'");let r=De(e.apiUrl?.trim()||Re),n={apiKey:t,apiUrl:r,botName:w(e.botName?.trim(),"Assistant",60),welcomeMessage:w(e.welcomeMessage?.trim(),"Hi! Ask me anything about this site.",400),showBranding:$e(e.showBranding,!0),primaryColor:L(e.primaryColor?.trim(),Pe),position:O(e.position?.trim()),avatarUrl:null,colorMode:"light",background:null,surface:null,foreground:null,muted:null,border:null,primaryForeground:null,darkOverrides:null,fontFamily:"system",displayFont:null,baseFontSize:"md",radius:"md",density:"comfortable",launcherShape:"circle",launcherSize:"md",panelSize:"md",launcherIcon:"chat",launcherIconUrl:null,showAvatarInMessages:!0,brandingText:null},a=e.botId?.trim();return a&&(n.botId=a),n}function de(e){return!!e&&typeof e=="object"&&!Array.isArray(e)}function Be(e){return!(!de(e)||typeof e.id!="string"||typeof e.slug!="string"||typeof e.name!="string"||typeof e.welcome_message!="string"||!de(e.widget_config))}async function M(e,t,r){let a=`${e.replace(/\/+$/,"")}/api/v1/bots/public/${encodeURIComponent(t)}`;try{let s=await fetch(a,{method:"GET",cache:"force-cache",credentials:"omit",mode:"cors",...r?{signal:r}:{}});if(!s.ok)return null;let i=await s.json();return Be(i)?i:null}catch{return null}}function ue(e){if(!e)return null;let t={background:g(e.background??void 0),surface:g(e.surface??void 0),foreground:g(e.foreground??void 0),muted:g(e.muted??void 0),border:g(e.border??void 0),primary:g(e.primary??void 0),primaryForeground:g(e.primary_foreground??void 0)};return Object.values(t).some(n=>n!==null)?t:null}function ce(e,t,r){let n={...e},a=r.widget_config;return t.botName===void 0&&(n.botName=w(r.name,e.botName,60)),t.welcomeMessage===void 0&&(n.welcomeMessage=w(r.welcome_message,e.welcomeMessage,400)),t.primaryColor===void 0&&a.primary_color&&(n.primaryColor=L(a.primary_color,e.primaryColor)),t.position===void 0&&a.position&&(n.position=O(a.position,e.position)),n.avatarUrl=A(a.avatar_url)??e.avatarUrl??null,n.colorMode=B(a.color_mode,e.colorMode),n.background=g(a.background)??e.background??null,n.surface=g(a.surface)??e.surface??null,n.foreground=g(a.foreground)??e.foreground??null,n.muted=g(a.muted)??e.muted??null,n.border=g(a.border)??e.border??null,n.primaryForeground=g(a.primary_foreground)??e.primaryForeground??null,n.darkOverrides=ue(a.dark_overrides??null)??e.darkOverrides??null,n.fontFamily=H(a.font_family,e.fontFamily),n.displayFont=K(a.display_font)??e.displayFont??null,n.baseFontSize=k(a.base_font_size,e.baseFontSize),n.radius=G(a.radius,e.radius),n.density=j(a.density,e.density),n.launcherShape=q(a.launcher_shape,e.launcherShape),n.launcherSize=k(a.launcher_size,e.launcherSize),n.panelSize=k(a.panel_size,e.panelSize),n.launcherIcon=Y(a.launcher_icon,e.launcherIcon),n.launcherIconUrl=A(a.launcher_icon_url)??e.launcherIconUrl??null,n.showAvatarInMessages=typeof a.show_avatar_in_messages=="boolean"?a.show_avatar_in_messages:e.showAvatarInMessages,n.brandingText=J(a.branding_text)??e.brandingText??null,n}function V(e,t){let r=t.widget_config;return{apiKey:e.apiKey,apiUrl:e.apiUrl,botId:e.botId,botName:w(t.name,"Assistant",60),welcomeMessage:w(t.welcome_message,"Hi!",400),showBranding:e.showBranding??!0,primaryColor:L(r.primary_color,"#0f172a"),position:O(r.position),avatarUrl:A(r.avatar_url),colorMode:B(r.color_mode),background:g(r.background),surface:g(r.surface),foreground:g(r.foreground),muted:g(r.muted),border:g(r.border),primaryForeground:g(r.primary_foreground),darkOverrides:ue(r.dark_overrides??null),fontFamily:H(r.font_family),displayFont:K(r.display_font),baseFontSize:k(r.base_font_size),radius:G(r.radius),density:j(r.density),launcherShape:q(r.launcher_shape),launcherSize:k(r.launcher_size),panelSize:k(r.panel_size),launcherIcon:Y(r.launcher_icon),launcherIconUrl:A(r.launcher_icon_url),showAvatarInMessages:typeof r.show_avatar_in_messages=="boolean"?r.show_avatar_in_messages:!0,brandingText:J(r.branding_text)}}function He(e){return{Authorization:`Bearer ${e}`,"Content-Type":"application/json",Accept:"text/event-stream"}}async function fe(e){let t=`${e.apiUrl}/api/v1/chat`,r=await fetch(t,{method:"POST",headers:He(e.apiKey),body:JSON.stringify(e.body),credentials:"omit",mode:"cors",...e.signal?{signal:e.signal}:{}});return!r.ok||!r.body?{ok:!1,status:r.status,events:Ke()}:{ok:!0,status:r.status,events:Ge(r.body)}}async function*Ke(){}async function*Ge(e){let t=e.getReader(),r=new TextDecoder("utf-8"),n="";try{for(;;){let{value:s,done:i}=await t.read();if(i)break;n+=r.decode(s,{stream:!0});let u;for(;(u=n.indexOf(`

`))!==-1;){let p=n.slice(0,u);n=n.slice(u+2);let m=ge(p);if(m===null)continue;let b=me(m);b&&(yield b)}}let a=n.trim();if(a){let s=ge(a);if(s!==null){let i=me(s);i&&(yield i)}}}finally{try{t.releaseLock()}catch{}}}function ge(e){let t=e.split(`
`),r=[];for(let n of t)n.startsWith("data:")&&r.push(n.slice(5).replace(/^ /,""));return r.length===0?null:r.join(`
`)}function me(e){try{let t=JSON.parse(e);return t&&typeof t=="object"&&typeof t.type=="string"?t:null}catch{return null}}var S={background:"#ffffff",surface:"#f8fafc",foreground:"#0f172a",muted:"#64748b",border:"rgba(15, 23, 42, 0.08)",primaryForeground:"#ffffff"},I={background:"#0a0a0c",surface:"#16161a",foreground:"#f1f1f3",muted:"#9aa0aa",border:"rgba(241, 241, 243, 0.10)",primaryForeground:"#ffffff"},pe={sm:13,md:14,lg:15},he={none:{msg:0,panel:0},sm:{msg:6,panel:8},md:{msg:12,panel:14},lg:{msg:18,panel:20},full:{msg:22,panel:28}},be={compact:{panel:10,gap:6},comfortable:{panel:14,gap:10},spacious:{panel:18,gap:14}},ye={sm:48,md:56,lg:64},je={circle:e=>Math.floor(e/2),"rounded-square":()=>14,pill:e=>Math.floor(e/2)},xe={sm:{w:340,h:500},md:{w:380,h:560},lg:{w:440,h:640}};function h(e,t){return e??t}function ve(e,t){return{...e,background:h(t?.background,I.background),surface:h(t?.surface,I.surface),foreground:h(t?.foreground,I.foreground),muted:h(t?.muted,I.muted),border:h(t?.border,I.border),primary:h(t?.primary,e.primary),primaryForeground:h(t?.primaryForeground,I.primaryForeground)}}function we(e){let t=he[e.radius]??he.md,r=be[e.density]??be.comfortable,n=xe[e.panelSize]??xe.md,a=ye[e.launcherSize]??ye.md,s=je[e.launcherShape](a),i=pe[e.baseFontSize]??pe.md,u=e.colorMode==="dark"?"mrag-mode-dark":e.colorMode==="auto"?"mrag-mode-auto":"mrag-mode-light";return{background:h(e.background,S.background),surface:h(e.surface,S.surface),foreground:h(e.foreground,S.foreground),muted:h(e.muted,S.muted),border:h(e.border,S.border),primary:e.primaryColor,primaryForeground:h(e.primaryForeground,S.primaryForeground),fontStack:$(e.fontFamily),displayFontStack:e.displayFont?$(e.displayFont):null,baseFontSizePx:i,radiusMessagePx:t.msg,radiusPanelPx:t.panel,panelPaddingPx:r.panel,messageGapPx:r.gap,panelWidthPx:n.w,panelHeightPx:n.h,launcherSizePx:a,launcherRadiusPx:s,colorModeClass:u}}function ke(e){let t=e.tokens,r=ve(t,e.darkOverrides),n=t.displayFontStack??t.fontStack;return`
:host {
  --mrag-bg: ${t.background};
  --mrag-surface: ${t.surface};
  --mrag-fg: ${t.foreground};
  --mrag-muted: ${t.muted};
  --mrag-border: ${t.border};
  --mrag-primary: ${t.primary};
  --mrag-primary-fg: ${t.primaryForeground};
  --mrag-radius-msg: ${t.radiusMessagePx}px;
  --mrag-radius-panel: ${t.radiusPanelPx}px;
  --mrag-launcher-size: ${t.launcherSizePx}px;
  --mrag-launcher-radius: ${t.launcherRadiusPx}px;
  --mrag-panel-w: ${t.panelWidthPx}px;
  --mrag-panel-h: ${t.panelHeightPx}px;
  --mrag-pad: ${t.panelPaddingPx}px;
  --mrag-gap: ${t.messageGapPx}px;
  --mrag-fs: ${t.baseFontSizePx}px;
  --mrag-font: ${t.fontStack};
  --mrag-display-font: ${n};

  all: initial;
  font-family: var(--mrag-font);
  color: var(--mrag-fg);
  font-size: var(--mrag-fs);
  line-height: 1.5;
}

/* Explicit dark mode (color_mode = "dark"). Tokens already point at the
 * dark palette via :host above (set by buildThemeTokens caller), but we
 * also expose this class so :host(.mrag-mode-dark) consumers can target
 * dark-only rules if needed. */
:host(.mrag-mode-dark) {
  --mrag-bg: ${r.background};
  --mrag-surface: ${r.surface};
  --mrag-fg: ${r.foreground};
  --mrag-muted: ${r.muted};
  --mrag-border: ${r.border};
  --mrag-primary: ${r.primary};
  --mrag-primary-fg: ${r.primaryForeground};
}

/* Auto: follow the host page's prefers-color-scheme. */
@media (prefers-color-scheme: dark) {
  :host(.mrag-mode-auto) {
    --mrag-bg: ${r.background};
    --mrag-surface: ${r.surface};
    --mrag-fg: ${r.foreground};
    --mrag-muted: ${r.muted};
    --mrag-border: ${r.border};
    --mrag-primary: ${r.primary};
    --mrag-primary-fg: ${r.primaryForeground};
  }
}

* {
  box-sizing: border-box;
}

.mrag-launcher {
  position: fixed;
  bottom: 20px;
  width: var(--mrag-launcher-size);
  height: var(--mrag-launcher-size);
  border-radius: var(--mrag-launcher-radius);
  border: none;
  background: var(--mrag-primary);
  color: var(--mrag-primary-fg);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.18);
  z-index: 2147483646;
  transition: transform 160ms ease;
  overflow: hidden;
}
.mrag-launcher:hover { transform: translateY(-1px); }
.mrag-launcher:focus-visible {
  outline: 2px solid var(--mrag-primary);
  outline-offset: 3px;
}
.mrag-launcher svg { width: 24px; height: 24px; }
.mrag-launcher img {
  width: 60%;
  height: 60%;
  object-fit: contain;
}

.mrag-pos-right { right: 20px; }
.mrag-pos-left  { left: 20px; }

.mrag-panel {
  position: fixed;
  bottom: calc(var(--mrag-launcher-size) + 30px);
  width: var(--mrag-panel-w);
  max-width: calc(100vw - 24px);
  height: var(--mrag-panel-h);
  max-height: calc(100vh - 110px);
  background: var(--mrag-bg);
  border: 1px solid var(--mrag-border);
  border-radius: var(--mrag-radius-panel);
  box-shadow: 0 20px 60px rgba(15, 23, 42, 0.16);
  display: none;
  flex-direction: column;
  overflow: hidden;
  z-index: 2147483647;
}
.mrag-panel[data-open="true"] { display: flex; }

.mrag-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid var(--mrag-border);
  background: var(--mrag-primary);
  color: var(--mrag-primary-fg);
}
.mrag-header h2 {
  font-family: var(--mrag-display-font);
  font-size: 14px;
  font-weight: 600;
  margin: 0;
  letter-spacing: -0.01em;
}
.mrag-close {
  background: transparent;
  border: 0;
  color: var(--mrag-primary-fg);
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  line-height: 0;
}
.mrag-close:hover { background: rgba(255, 255, 255, 0.15); }
.mrag-close:focus-visible { outline: 2px solid currentColor; outline-offset: 1px; }

.mrag-messages {
  flex: 1 1 auto;
  overflow-y: auto;
  padding: var(--mrag-pad);
  display: flex;
  flex-direction: column;
  gap: var(--mrag-gap);
  background: var(--mrag-surface);
}

.mrag-msg-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.mrag-msg-row.is-user {
  flex-direction: row-reverse;
}

.mrag-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  flex-shrink: 0;
  overflow: hidden;
  background: var(--mrag-primary);
  color: var(--mrag-primary-fg);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
}
.mrag-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.mrag-msg {
  max-width: 85%;
  padding: 9px 12px;
  border-radius: var(--mrag-radius-msg);
  word-wrap: break-word;
  white-space: pre-wrap;
  font-size: var(--mrag-fs);
}
.mrag-msg-user {
  align-self: flex-end;
  background: var(--mrag-primary);
  color: var(--mrag-primary-fg);
  border-bottom-right-radius: 4px;
}
.mrag-msg-assistant {
  align-self: flex-start;
  background: var(--mrag-bg);
  border: 1px solid var(--mrag-border);
  border-bottom-left-radius: 4px;
}
.mrag-msg-system {
  align-self: center;
  background: transparent;
  color: var(--mrag-muted);
  font-size: 12px;
  font-style: italic;
}
.mrag-msg-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
}
.mrag-retry {
  display: inline-flex;
  align-items: center;
  margin-top: 6px;
  padding: 4px 10px;
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  background: #fff;
  color: #991b1b;
  border: 1px solid #fecaca;
  border-radius: 8px;
  cursor: pointer;
  transition: background 120ms ease;
}
.mrag-retry:hover { background: #fef2f2; }
.mrag-retry:focus-visible {
  outline: 2px solid #991b1b;
  outline-offset: 2px;
}

.mrag-typing {
  display: inline-flex;
  gap: 4px;
  padding: 6px 0;
}
.mrag-typing span {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--mrag-muted);
  animation: mrag-bounce 1.2s infinite ease-in-out;
}
.mrag-typing span:nth-child(2) { animation-delay: 0.15s; }
.mrag-typing span:nth-child(3) { animation-delay: 0.3s; }

@keyframes mrag-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
  30% { transform: translateY(-4px); opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .mrag-launcher { transition: none; }
  .mrag-typing span { animation: none; opacity: 0.7; }
  .mrag-retry { transition: none; }
}

.mrag-sources {
  margin-top: 6px;
  font-size: 12px;
}
.mrag-sources summary {
  cursor: pointer;
  color: var(--mrag-muted);
  user-select: none;
}
.mrag-sources summary:hover { color: var(--mrag-fg); }
.mrag-sources ul {
  list-style: none;
  margin: 6px 0 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.mrag-sources li {
  background: var(--mrag-surface);
  border: 1px solid var(--mrag-border);
  border-radius: 8px;
  padding: 6px 8px;
}
.mrag-sources .mrag-src-title {
  font-weight: 600;
  font-size: 12px;
}
.mrag-sources .mrag-src-snippet {
  color: var(--mrag-muted);
  font-size: 11px;
  margin-top: 2px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.mrag-form {
  display: flex;
  gap: 8px;
  padding: 10px;
  border-top: 1px solid var(--mrag-border);
  background: var(--mrag-bg);
}
.mrag-input {
  flex: 1;
  padding: 9px 12px;
  font: inherit;
  color: inherit;
  background: var(--mrag-surface);
  border: 1px solid var(--mrag-border);
  border-radius: 10px;
  outline: none;
  resize: none;
  max-height: 120px;
  min-height: 38px;
}
.mrag-input:focus {
  border-color: var(--mrag-primary);
  box-shadow: 0 0 0 3px rgba(15, 23, 42, 0.06);
}
.mrag-input:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}
.mrag-send {
  background: var(--mrag-primary);
  color: var(--mrag-primary-fg);
  border: 0;
  border-radius: 10px;
  padding: 0 14px;
  cursor: pointer;
  font: inherit;
  font-weight: 600;
}
.mrag-send:disabled { opacity: 0.5; cursor: not-allowed; }
.mrag-send:focus-visible { outline: 2px solid var(--mrag-primary); outline-offset: 2px; }

.mrag-footer {
  text-align: center;
  font-size: 11px;
  color: var(--mrag-muted);
  padding: 6px 0 8px 0;
  border-top: 1px solid var(--mrag-border);
  background: var(--mrag-bg);
}
.mrag-footer a {
  color: var(--mrag-muted);
  text-decoration: none;
}
.mrag-footer a:hover { text-decoration: underline; }

.mrag-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 12px;
  margin: 8px 14px;
}

@media (max-width: 480px) {
  .mrag-panel {
    width: calc(100vw - 16px);
    height: calc(100vh - 100px);
    bottom: calc(var(--mrag-launcher-size) + 24px);
  }
  .mrag-pos-right { right: 8px; }
  .mrag-pos-left  { left: 8px; }
}
`}var W=class{constructor(t,r,n={}){this.target=t;this.onUpdate=r;this.buffer="";this.rafId=null;this.timerId=null;this.lastTick=0;this.destroyed=!1;this.tick=t=>{if(this.destroyed){this.rafId=null;return}let r=Math.max(0,(t-this.lastTick)/1e3);this.lastTick=t;let n=Math.max(1,Math.floor(this.cps*r));if(this.buffer.length===0){this.rafId=null;return}let a=this.buffer.slice(0,n);this.buffer=this.buffer.slice(n),this.target.content+=a,this.onUpdate(),this.buffer.length>0?this.rafId=this.raf(this.tick):this.rafId=null};this.cps=n.cps??600,this.dwellMs=n.dwellMs??150,this.now=n.now??(()=>performance.now()),this.raf=n.raf??(a=>requestAnimationFrame(a)),this.cancelRaf=n.cancelRaf??(a=>cancelAnimationFrame(a)),this.setTimeoutFn=n.setTimeout??((a,s)=>setTimeout(a,s)),this.clearTimeoutFn=n.clearTimeout??(a=>clearTimeout(a)),this.reduced=n.reducedMotion??this.detectReducedMotion(),this.startedAt=this.now()}push(t){if(!this.destroyed&&t){if(this.buffer+=t,this.reduced){this.flushImmediate();return}this.scheduleStart()}}flushImmediate(){this.destroyed||(this.rafId!==null&&(this.cancelRaf(this.rafId),this.rafId=null),this.timerId!==null&&(this.clearTimeoutFn(this.timerId),this.timerId=null),this.buffer.length!==0&&(this.target.content+=this.buffer,this.buffer="",this.onUpdate()))}destroy(){this.destroyed=!0,this.rafId!==null&&(this.cancelRaf(this.rafId),this.rafId=null),this.timerId!==null&&(this.clearTimeoutFn(this.timerId),this.timerId=null),this.buffer=""}hasPending(){return this.buffer.length>0}scheduleStart(){if(this.rafId!==null||this.timerId!==null)return;let t=this.now()-this.startedAt;if(t>=this.dwellMs){this.startTick();return}let r=this.dwellMs-t;this.timerId=this.setTimeoutFn(()=>{this.timerId=null,!this.destroyed&&this.startTick()},r)}startTick(){this.lastTick=this.now(),this.rafId=this.raf(this.tick)}detectReducedMotion(){if(typeof window>"u"||typeof window.matchMedia!="function")return!1;try{return window.matchMedia("(prefers-reduced-motion: reduce)").matches}catch{return!1}}};var Te="mongorag.conversation_id:",Ce="http://www.w3.org/2000/svg";function qe(e,t,r){let n={message:t};return r&&(n.conversation_id=r),e.botId&&(n.bot_id=e.botId),n}function R(e,t={}){let r={...e},n=document.createElement("div");n.setAttribute("data-mongorag-widget",""),n.style.cssText="all: initial;",document.body.appendChild(n);let a=n.attachShadow({mode:"closed"});function s(o){n.classList.remove("mrag-mode-light","mrag-mode-dark","mrag-mode-auto"),n.classList.add(`mrag-mode-${o}`)}s(r.colorMode);let i=document.createElement("link");i.rel="stylesheet";function u(o){if(ne()){i.parentNode&&i.parentNode.removeChild(i);return}let f=o.displayFont?[o.fontFamily,o.displayFont]:[o.fontFamily],c=re(f);if(!c){i.parentNode&&i.parentNode.removeChild(i);return}i.href!==c&&(i.href=c),i.parentNode||a.appendChild(i)}u(r);let p=document.createElement("style");function m(o){p.textContent=ke({tokens:we(o),darkOverrides:o.darkOverrides??null})}m(r),a.appendChild(p);let b=Je(r),d=Ve(r);a.appendChild(b),a.appendChild(d.element);let l={open:!1,sending:!1,messages:[],abort:null,reveal:null,lastUserText:"",conversationId:rt(r.apiKey)};function N(){l.reveal&&(l.reveal.destroy(),l.reveal=null),l.abort&&(l.abort.abort(),l.abort=null)}function U(o){l.open=o,d.element.dataset.open=String(o),b.setAttribute("aria-expanded",String(o)),o?(l.messages.length===0&&(l.messages.push({role:"assistant",content:r.welcomeMessage}),y()),requestAnimationFrame(()=>d.input.focus())):N()}function y(){d.messages.textContent="";for(let o of l.messages)d.messages.appendChild(Xe(o,r));d.messages.scrollTop=d.messages.scrollHeight}function Me(o){let f=r;if(r=o,m(o),s(o.colorMode),u(o),f.botName!==o.botName&&(d.title.textContent=o.botName,d.element.setAttribute("aria-label",`${o.botName} chat`)),Ae(b,o),f.position!==o.position){let c=`mrag-pos-${f.position==="bottom-left"?"left":"right"}`,_=`mrag-pos-${o.position==="bottom-left"?"left":"right"}`;d.element.classList.remove(c),d.element.classList.add(_)}d.brandingLink&&(d.brandingLink.textContent=o.brandingText??"Powered by MongoRAG"),f.welcomeMessage!==o.welcomeMessage&&l.messages.length===1&&l.messages[0]?.role==="assistant"&&l.messages[0]?.content===f.welcomeMessage&&(l.messages[0].content=o.welcomeMessage),y(),t.onConfigUpdate?.(o)}async function ee(o){let f=o.trim();if(!f)return;N(),l.sending&&(l.sending=!1),l.sending=!0,l.lastUserText=f,d.send.disabled=!0,d.input.disabled=!0,l.messages.push({role:"user",content:f});let c={role:"assistant",content:"",pending:!0};l.messages.push(c),y();let _=qe(r,f,l.conversationId),P=new AbortController;l.abort=P;let v=new W(c,()=>y());l.reveal=v;try{let C=await fe({apiUrl:r.apiUrl,apiKey:r.apiKey,body:_,signal:P.signal});if(!C.ok){v.destroy(),X(c,tt(C.status)),y();return}let T=!1;for await(let F of C.events){if(P.signal.aborted)break;if(F.type==="token"&&typeof F.content=="string"){v.push(F.content),c.pending=!0,T=!0;continue}v.flushImmediate(),et(F,c,te=>{l.conversationId=te,nt(r.apiKey,te)}),y()}v.flushImmediate(),!T&&!c.content?(X(c,"No response received. Please try again."),y()):c.pending&&(c.pending=!1,y())}catch(C){if(C instanceof DOMException&&C.name==="AbortError"){if(c.content)c.pending=!1;else{let T=l.messages.indexOf(c);T!==-1&&l.messages.splice(T,1)}y();return}v.destroy(),X(c,"Couldn't reach the server. Check your connection and try again."),y()}finally{l.sending=!1,l.abort===P&&(l.abort=null),l.reveal===v&&(l.reveal=null),d.send.disabled=!1,d.input.disabled=!1,d.input.focus()}}function Ee(){let o=l.lastUserText;o&&ee(o)}if(r.botId&&t.rawInput&&(t.fetchPublic||M)){let o=t.fetchPublic??M,f=t.rawInput;o(r.apiUrl,r.botId).then(c=>{if(c===null)return;let _=ce(r,f,c);Me(_)}).catch(()=>{})}return b.addEventListener("click",()=>U(!l.open)),d.close.addEventListener("click",()=>U(!1)),d.form.addEventListener("submit",o=>{o.preventDefault();let f=d.input.value;d.input.value="",_e(d.input),ee(f)}),d.input.addEventListener("keydown",o=>{o.key==="Enter"&&!o.shiftKey&&(o.preventDefault(),d.form.requestSubmit()),o.key==="Escape"&&(U(!1),b.focus())}),d.input.addEventListener("input",()=>_e(d.input)),d.messages.addEventListener("click",o=>{let f=o.target;if(!(f instanceof Element))return;f.closest("[data-mrag-retry]")&&(o.preventDefault(),Ee())}),{destroy(){N(),n.remove()}}}function X(e,t){e.pending=!1,e.content=t,e.error=!0}function E(e){let t=document.createElementNS(Ce,"svg");t.setAttribute("viewBox","0 0 24 24"),t.setAttribute("fill","none"),t.setAttribute("stroke","currentColor"),t.setAttribute("stroke-width","2"),t.setAttribute("stroke-linecap","round"),t.setAttribute("stroke-linejoin","round"),t.setAttribute("aria-hidden","true");for(let r of e){let n=document.createElementNS(Ce,r.tag);for(let[a,s]of Object.entries(r.attrs))n.setAttribute(a,s);t.appendChild(n)}return t}var Se={chat:()=>E([{tag:"path",attrs:{d:"M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"}}]),sparkle:()=>E([{tag:"path",attrs:{d:"M12 3v18"}},{tag:"path",attrs:{d:"M3 12h18"}},{tag:"path",attrs:{d:"M5.6 5.6l12.8 12.8"}},{tag:"path",attrs:{d:"M18.4 5.6L5.6 18.4"}}]),book:()=>E([{tag:"path",attrs:{d:"M4 4h12a4 4 0 0 1 4 4v12H8a4 4 0 0 1-4-4V4z"}},{tag:"path",attrs:{d:"M4 16a4 4 0 0 1 4-4h12"}}]),question:()=>E([{tag:"circle",attrs:{cx:"12",cy:"12",r:"10"}},{tag:"path",attrs:{d:"M9.5 9a2.5 2.5 0 0 1 5 0c0 1.5-2.5 2-2.5 4"}},{tag:"line",attrs:{x1:"12",y1:"17",x2:"12",y2:"17.01"}}])};function Ye(e){if(e.launcherIcon==="custom"&&e.launcherIconUrl){let r=document.createElement("img");return r.src=e.launcherIconUrl,r.alt="",r.setAttribute("aria-hidden","true"),r.loading="lazy",r.onerror=()=>{let n=r.parentNode;n&&n.replaceChild(Se.chat(),r)},r}let t=e.launcherIcon==="custom"?"chat":e.launcherIcon;return Se[t]()}function Je(e){let t=document.createElement("button");return t.type="button",Ae(t,e),t}function Ae(e,t){for(e.className=`mrag-launcher mrag-pos-${t.position==="bottom-left"?"left":"right"}`,e.setAttribute("aria-label",`Open chat with ${t.botName}`),e.setAttribute("aria-haspopup","dialog"),e.setAttribute("aria-expanded",e.getAttribute("aria-expanded")??"false");e.firstChild;)e.removeChild(e.firstChild);e.appendChild(Ye(t))}function Ve(e){let t=document.createElement("div");t.className=`mrag-panel mrag-pos-${e.position==="bottom-left"?"left":"right"}`,t.setAttribute("role","dialog"),t.setAttribute("aria-label",`${e.botName} chat`),t.setAttribute("aria-modal","false");let r=document.createElement("div");r.className="mrag-header";let n=document.createElement("h2");n.textContent=e.botName;let a=document.createElement("button");a.type="button",a.className="mrag-close",a.setAttribute("aria-label","Close chat"),a.appendChild(E([{tag:"line",attrs:{x1:"18",y1:"6",x2:"6",y2:"18"}},{tag:"line",attrs:{x1:"6",y1:"6",x2:"18",y2:"18"}}])),r.append(n,a);let s=document.createElement("div");s.className="mrag-messages",s.setAttribute("role","log"),s.setAttribute("aria-live","polite"),s.setAttribute("aria-relevant","additions");let i=document.createElement("form");i.className="mrag-form",i.setAttribute("aria-label","Send message");let u=document.createElement("textarea");u.className="mrag-input",u.placeholder="Type your message\u2026",u.setAttribute("aria-label","Message"),u.rows=1,u.maxLength=2e3;let p=document.createElement("button");p.type="submit",p.className="mrag-send",p.textContent="Send",i.append(u,p),t.append(r,s,i);let m=null;if(e.showBranding){let b=document.createElement("div");b.className="mrag-footer",m=document.createElement("a"),m.href="https://mongorag.com",m.target="_blank",m.rel="noopener noreferrer",m.textContent=e.brandingText??"Powered by MongoRAG",b.appendChild(m),t.appendChild(b)}return{element:t,title:n,messages:s,form:i,input:u,send:p,close:a,brandingLink:m}}function Xe(e,t){let r=document.createElement("div");if(r.className=`mrag-msg mrag-msg-${e.role}`,e.error&&r.classList.add("mrag-msg-error"),e.pending&&!e.content){let n=document.createElement("div");n.className="mrag-typing",n.setAttribute("aria-label","Assistant is typing");for(let a=0;a<3;a++)n.appendChild(document.createElement("span"));r.appendChild(n)}else{let n=document.createElement("div");if(n.textContent=e.content,r.appendChild(n),e.error){let a=document.createElement("button");a.type="button",a.className="mrag-retry",a.textContent="Retry",a.setAttribute("data-mrag-retry",""),a.setAttribute("aria-label","Retry the last message"),r.appendChild(a)}e.role==="assistant"&&e.sources&&e.sources.length>0&&r.appendChild(Qe(e.sources))}if(e.role==="assistant"&&t?.showAvatarInMessages&&!e.error){let n=document.createElement("div");n.className="mrag-msg-row";let a=Ze(t);return n.append(a,r),n}return r}function Ze(e){let t=document.createElement("div");if(t.className="mrag-avatar",e.avatarUrl){let r=document.createElement("img");r.src=e.avatarUrl,r.alt="",r.loading="lazy",r.setAttribute("aria-hidden","true"),r.onerror=()=>{let n=r.parentNode;n&&(n.removeChild(r),n.appendChild(Ie(e.botName)))},t.appendChild(r)}else t.appendChild(Ie(e.botName));return t}function Ie(e){let t=(e??"").trim(),r=t.length>0?t[0].toUpperCase():"?";return document.createTextNode(r)}function Qe(e){let t=document.createElement("details");t.className="mrag-sources";let r=document.createElement("summary");r.textContent=`${e.length} source${e.length===1?"":"s"}`,t.appendChild(r);let n=document.createElement("ul");for(let a of e.slice(0,8)){let s=document.createElement("li"),i=document.createElement("div");i.className="mrag-src-title";let u=Array.isArray(a.heading_path)?a.heading_path.join(" \u203A "):"",p=a.document_title||"Source";if(i.textContent=u?`${p} \u2014 ${u}`:p,s.appendChild(i),a.snippet){let m=document.createElement("div");m.className="mrag-src-snippet",m.textContent=a.snippet,s.appendChild(m)}n.appendChild(s)}return t.appendChild(n),t}function et(e,t,r){switch(e.type){case"token":typeof e.content=="string"&&(t.content+=e.content,t.pending=!0);break;case"sources":Array.isArray(e.sources)&&(t.sources=e.sources);break;case"done":t.pending=!1,typeof e.conversation_id=="string"&&e.conversation_id&&r(e.conversation_id);break;case"error":t.pending=!1,t.content=typeof e.message=="string"&&e.message?e.message:"Something went wrong.";break}}function tt(e){return e===401||e===403?"Authentication failed. Check your API key.":e===429?"Rate limit reached. Please try again in a moment.":e===503||e===502?"The service is temporarily unavailable.":e>=500?"Server error. Please try again.":"Something went wrong. Please try again."}function rt(e){try{return localStorage.getItem(Te+e)||void 0}catch{return}}function nt(e,t){try{localStorage.setItem(Te+e,t)}catch{}}function _e(e){e.style.height="auto";let t=120;e.style.height=Math.min(e.scrollHeight,t)+"px"}var Z=!1;function Q(e){typeof console<"u"&&console.warn&&console.warn(`[MongoRAG] ${e}`)}function at(){if(Z)return;let e=document.currentScript,t=e?.dataset.previewTokens;if(t)try{let u=JSON.parse(t),p=e?.dataset.apiUrl??"https://api.mongorag.com",m=V({apiKey:"preview-no-auth",apiUrl:p,showBranding:!0},u);Z=!0,ot(m);return}catch{Q("Could not parse data-preview-tokens; skipping preview boot")}let r=e?ie(e):void 0,n=window.MongoRAG??void 0,a=se(n,r),s;try{s=le(a)}catch(u){u instanceof x?Q(u.message):Q("Failed to initialize widget");return}Z=!0;let i={rawInput:a,fetchPublic:M};document.readyState==="loading"?document.addEventListener("DOMContentLoaded",()=>R(s,i),{once:!0}):R(s,i)}function ot(e){let t=()=>{let r=R(e),n=window.MongoRAG??{};n.bootWithConfig=a=>{r.destroy();let s=V({apiKey:e.apiKey,apiUrl:e.apiUrl,showBranding:e.showBranding},a);R(s)},window.MongoRAG=n,requestAnimationFrame(()=>{})};document.readyState==="loading"?document.addEventListener("DOMContentLoaded",t,{once:!0}):t()}typeof window<"u"&&at();})();
