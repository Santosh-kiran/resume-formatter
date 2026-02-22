'use client'
import { useState } from 'react'

export default function Home() {
  const [file, setFile] = useState(null)

  const handleUpload = async () => {
    if (!file) return alert("Upload a file")

    const formData = new FormData()
    formData.append("file", file)

    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/upload`,
      {
        method: "POST",
        body: formData
      }
    )

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
      <br /><br />
      <button onClick={handleUpload}>Generate</button>
    </div>
  )
}
