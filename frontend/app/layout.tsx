import type { Metadata } from "next";
import "./fonts/fonts.css"; // Inter, JetBrains Mono — локал (Google Fonts руу хандахгүй)
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "AI Ресепшн", template: "%s · AI Ресепшн" },
  description: "Байгууллагын монгол утасны AI ресепшнийг удирдах самбар",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="mn" className="h-full antialiased">
      <body className="min-h-full bg-bg font-sans text-[15px] leading-normal text-fg">{children}</body>
    </html>
  );
}
