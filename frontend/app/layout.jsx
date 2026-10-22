import { AuthProvider } from "../src/auth";
import "../src/site/site.css";

export const viewport = {
  themeColor: "#060a13",
};

export const metadata = {
  title: "NOVI — Your Success OS",
  description:
    "NOVI — the Operating System for Student Success. AI mentoring from Grade 9 to your dream university.",
  icons: {
    icon: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop offset='0' stop-color='%238b6cff'/%3E%3Cstop offset='1' stop-color='%234ac7f0'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='64' height='64' rx='16' fill='url(%23g)'/%3E%3Ctext x='32' y='44' font-family='Arial, sans-serif' font-size='34' font-weight='800' fill='%230a0d14' text-anchor='middle'%3EN%3C/text%3E%3C/svg%3E",
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var p=JSON.parse(localStorage.getItem("novi_prefs")||"{}")||{};var t=p.theme;if(t!=="light"&&t!=="dark"){t=(window.matchMedia&&window.matchMedia("(prefers-color-scheme: light)").matches)?"light":"dark";}document.documentElement.setAttribute("data-theme",t);var m=document.querySelector('meta[name="theme-color"]');if(m)m.setAttribute("content",t==="light"?"#f3f5fb":"#060a13");}catch(e){document.documentElement.setAttribute("data-theme","dark");}})();`,
          }}
        />
      </head>
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
