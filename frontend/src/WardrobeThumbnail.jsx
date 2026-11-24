import { useState } from 'react'
import { describeWardrobeImage } from './wardrobeAppearance.js'
import { wardrobeImageBounds } from './wardrobeImageBounds.js'
import { resolveWardrobeImage } from './wardrobeImages.js'
import blueTop from './assets/icons/wardrobe-top-blue.png'
import greenTop from './assets/icons/wardrobe-top-green.png'
import yellowTop from './assets/icons/wardrobe-top-yellow.png'
import './WardrobeThumbnail.css'

const LEGACY = { 'wardrobe-top-blue.png': blueTop, 'wardrobe-top-green.png': greenTop, 'wardrobe-top-yellow.png': yellowTop }

export default function WardrobeThumbnail({ item, className = '', fallback = null }) {
    const [failedUrl, setFailedUrl] = useState(null)
    const url = item?.image_url
    const legacy = url && !/^https?:/i.test(url) ? LEGACY[url.split('/').at(-1)] : null
    const src = legacy || resolveWardrobeImage(url)
    const bounds = wardrobeImageBounds[describeWardrobeImage(url)?.path]

    return <span className={'wardrobe-thumbnail ' + className} aria-hidden="true">
        {!src || failedUrl === src ? fallback : bounds ? <svg viewBox={bounds.join(' ')} focusable="false">
            <image href={src} width="1024" height="1536" onError={() => setFailedUrl(src)} />
        </svg> : <img src={src} alt="" onError={() => setFailedUrl(src)} />}
    </span>
}
