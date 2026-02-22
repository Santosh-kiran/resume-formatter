'use client'
import { useState } from 'react'

export default function Home() {
  const [file, setFile] = useState(null)

  const handleUpload = async () => {
    const formData = new FormData()
    formData.append("file", file)

    const response = await fetch("https://YOUR-RAILWAY-URL/upload", {
      method: "POST",
      body: formData
    })

    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "FormattedResume.docx"
    a.click()
  }

  return (
    <div style={{ padding: 40 }}>
      <h1>Resume Formatter</h1>
      <input type="file" onChange={(e) => setFile(e.target.files[0])} />
      <button onClick={handleUpload}>Generate</button>
    </div>
  )
}