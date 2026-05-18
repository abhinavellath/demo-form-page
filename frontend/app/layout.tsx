import './globals.css'

export const metadata = {
  title: 'AI Recruiter Demo',
  description: 'AI calling recruiter demo'
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}