function asciiFoldUpper(value) {
  const s = String(value || '').trim()
  if (!s) return ''
  return s
    .toLocaleUpperCase('tr-TR')
    .replaceAll('Ç', 'C')
    .replaceAll('Ğ', 'G')
    .replaceAll('İ', 'I')
    .replaceAll('Ö', 'O')
    .replaceAll('Ş', 'S')
    .replaceAll('Ü', 'U')
    .replace(/[\s_-]+/g, ' ')
    .trim()
}

export function normalizeKurum(value, daire = '') {
  const raw = asciiFoldUpper(value)
  if (raw) {
    const aliases = {
      YARGITAY: 'YARGITAY',
      DANISTAY: 'DANISTAY',
      UYUSMAZLIK: 'UYUSMAZLIK MAHKEMESI',
      'UYUSMAZLIK MAHKEMESI': 'UYUSMAZLIK MAHKEMESI',
      ANAYASA: 'ANAYASA MAHKEMESI',
      'ANAYASA MAHKEMESI': 'ANAYASA MAHKEMESI',
      'YARGITAY CGK': 'YARGITAY_CGK',
      'YARGITAY CEZA GENEL KURULU': 'YARGITAY_CGK',
      'CEZA GENEL KURULU': 'YARGITAY_CGK',
    }
    return aliases[raw] || raw
  }
  return inferKurumFromDaire(daire)
}

export function inferKurumFromDaire(daire) {
  const d = String(daire || '').trim().toLocaleLowerCase('tr-TR')
  if (d === 'yargıtay' || d === 'yargitay' || d.startsWith('yargıtay ') || d.startsWith('yargitay ')) return 'YARGITAY'
  if (d === 'danıştay' || d === 'danistay' || d.startsWith('danıştay ') || d.startsWith('danistay ')) return 'DANISTAY'
  if (d.startsWith('uyuşmazlık mahkemesi ') || d.startsWith('uyusmazlik mahkemesi ')) return 'UYUSMAZLIK MAHKEMESI'
  if (d === 'uyuşmazlık mahkemesi' || d === 'uyusmazlik mahkemesi') return 'UYUSMAZLIK MAHKEMESI'
  if (d.startsWith('anayasa mahkemesi ')) return 'ANAYASA MAHKEMESI'
  if (d === 'anayasa mahkemesi') return 'ANAYASA MAHKEMESI'
  return ''
}

export function getCourtDisplayName(kurum, daire = '') {
  const normalized = normalizeKurum(kurum, daire)
  if (!normalized) return ''
  const names = {
    YARGITAY: 'Yargıtay',
    DANISTAY: 'Danıştay',
    'UYUSMAZLIK MAHKEMESI': 'Uyuşmazlık Mahkemesi',
    'ANAYASA MAHKEMESI': 'Anayasa Mahkemesi',
    YARGITAY_CGK: 'Yargıtay Ceza Genel Kurulu',
  }
  return names[normalized] || normalized
}

export function stripKurumPrefixFromDaire(daire, kurum) {
  const k = normalizeKurum(kurum, daire)
  let d = String(daire || '').trim()
  const court = getCourtDisplayName(k, d)
  const low = d.toLocaleLowerCase('tr-TR')
  if (court && low === court.toLocaleLowerCase('tr-TR')) return ''
  if (k === 'YARGITAY' && (low.startsWith('yargıtay ') || low.startsWith('yargitay '))) {
    d = d.replace(/^(yargıtay|yargitay)\s+/i, '')
  } else if (k === 'DANISTAY' && (low.startsWith('danıştay ') || low.startsWith('danistay '))) {
    d = d.replace(/^(danıştay|danistay)\s+/i, '')
  } else if (k === 'UYUSMAZLIK MAHKEMESI' && (low.startsWith('uyuşmazlık mahkemesi ') || low.startsWith('uyusmazlik mahkemesi '))) {
    d = d.replace(/^(uyuşmazlık|uyusmazlik)\s+mahkemesi\s+/i, '')
  } else if (k === 'ANAYASA MAHKEMESI' && low.startsWith('anayasa mahkemesi ')) {
    d = d.replace(/^anayasa\s+mahkemesi\s+/i, '')
  }
  return d.trim()
}

export function buildCourtLabel({ kurum, daire }) {
  const d = stripKurumPrefixFromDaire(daire, kurum)
  const court = getCourtDisplayName(kurum, daire)
  if (court && d) return `${court} - ${d}`
  return court || d || ''
}
