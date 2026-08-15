import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ОценитьКвартиру — онлайн-оценка рыночной стоимости квартиры",
  description:
    "Бесплатная онлайн-оценка рыночной стоимости квартиры по адресу и параметрам. Анализ актуальных предложений на рынке.",
  openGraph: {
    title: "ОценитьКвартиру — онлайн-оценка рыночной стоимости квартиры",
    description:
      "Бесплатная онлайн-оценка рыночной стоимости квартиры по адресу и параметрам.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
