import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "UCA Data",
  description: "Explorer des données publiques de façon transparente",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
