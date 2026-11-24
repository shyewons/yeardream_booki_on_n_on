import { useEffect, useState } from 'react'
import { describeWardrobeImage, getAvatarAppearance } from './wardrobeAppearance.js'
import { resolveWardrobeImage, wardrobeImagePaths } from './wardrobeImages.js'
import regularBase from './assets/characters/child-base.png'
import capBase from './assets/characters/child-base-cap-compatible.png'
import './WardrobeAvatar.css'

const BASES = { regular: regularBase, 'cap-compatible': capBase }
const EMPTY = getAvatarAppearance()
const loadedImages = new Map()

function loadImage(url) {
    if (!loadedImages.has(url)) {
        const promise = new Promise((resolve) => {
            const image = new Image()
            image.onload = () => resolve(true)
            image.onerror = () => resolve(false)
            image.src = url
        }).then((loaded) => {
            if (!loaded) loadedImages.delete(url)
            return loaded
        })
        loadedImages.set(url, promise)
    }
    return loadedImages.get(url)
}

export default function WardrobeAvatar({ character = {} }) {
    const signature = JSON.stringify(character || {})
    const [ready, setReady] = useState({ signature: '', appearance: EMPTY, failed: false, baseLoaded: false })

    useEffect(() => {
        let cancelled = false
        const selected = JSON.parse(signature)
        async function prepare() {
            const paths = Object.values(selected).flatMap((item) => {
                const image = describeWardrobeImage(item?.image_url)
                return image && wardrobeImagePaths.has(image.path) ? [image.path] : []
            })
            const desired = getAvatarAppearance(selected, wardrobeImagePaths)
            const [regularLoaded, headLoaded, results] = await Promise.all([
                loadImage(regularBase),
                desired.base === 'cap-compatible' ? loadImage(capBase) : Promise.resolve(true),
                Promise.all(paths.map(async (path) => [path, await loadImage(resolveWardrobeImage('/images/wardrobe/' + path))])),
            ])
            const available = new Set(results.filter(([, loaded]) => loaded).map(([path]) => path))
            if (!headLoaded) {
                for (const path of available) {
                    if (describeWardrobeImage('/images/wardrobe/' + path)?.replacesHair) available.delete(path)
                }
            }
            const appearance = getAvatarAppearance(selected, available)
            const failed = !regularLoaded || !headLoaded || results.some(([, loaded]) => !loaded)
            // 지난 요청으로 착용을 되돌리지 않고, 기본형과 머리 장식을 함께 바꾼다.
            if (!cancelled) setReady({ signature, appearance, failed, baseLoaded: appearance.base === 'cap-compatible' ? headLoaded : regularLoaded })
        }
        prepare()
        return () => { cancelled = true }
    }, [signature])

    const { appearance } = ready
    const names = appearance.layers.map((layer) => layer.name).join(', ')
    return <div className="wardrobe-avatar-frame" aria-busy={ready.signature !== signature}>
        <div className="wardrobe-avatar" role="img" aria-hidden={!ready.baseLoaded} aria-label={names ? `내 캐릭터: ${names}` : '내 캐릭터 기본 모습'} data-one-piece={appearance.hiddenBottom}>
            {ready.baseLoaded && <>
                <img className="wardrobe-avatar__layer" src={BASES[appearance.base]} alt="" draggable="false" />
                {appearance.layers.map((layer) => <img key={layer.path} className="wardrobe-avatar__layer" data-slot={layer.slot}
                    style={{ zIndex: layer.zIndex }} src={resolveWardrobeImage('/images/wardrobe/' + layer.path)} alt="" draggable="false" />)}
            </>}
        </div>
        {ready.failed && <p className="wardrobe-avatar__notice" role="status">일부 옷 그림을 불러오지 못했어요.</p>}
    </div>
}
