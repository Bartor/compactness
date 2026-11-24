import { useEffect, useState } from 'react'

export const PHONE_QUERY = '(max-width: 760px)'

/** True on a phone-width screen (the sidebar is a sheet there); follows the window. */
export function usePhone() {
  const get = () => typeof window !== 'undefined' && window.matchMedia(PHONE_QUERY).matches
  const [phone, setPhone] = useState(get)
  useEffect(() => {
    const mq = window.matchMedia(PHONE_QUERY)
    const on = () => setPhone(mq.matches)
    on()
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])
  return phone
}
