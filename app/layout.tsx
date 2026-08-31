import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "MAGI SYSTEM",
  description: "MAGI decision analysis system",
  icons: {
    icon: "/nerv-logo.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}