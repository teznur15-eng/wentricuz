import type { Metadata } from "next";
import "./globals.css";
export const metadata:Metadata={title:"Wentric Management | Boshqaruv tizimi",description:"Wentric IT Group ichki boshqaruv platformasi"};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="uz"><body>{children}</body></html>}
