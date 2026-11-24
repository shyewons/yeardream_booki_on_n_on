const PREFIX = '/images/wardrobe/'
const MEADOW_SLOTS = {
    '01-hat-long-hair.png': 'hat',
    '02-striped-shirt.png': 'top',
    '03-green-skirt.png': 'bottom',
    '04-yellow-boots.png': 'shoes',
    '05-green-wristband.png': 'gloves',
}
const LAYERS = [['bottom', 10], ['top', 20], ['hat', 30], ['shoes', 40], ['gloves', 50]]

// DB의 의상 ID 대신 등록된 착용 이미지 경로와 부위로 연결한다.
export function describeWardrobeImage(imageUrl) {
    if (typeof imageUrl !== 'string' || !imageUrl.startsWith(PREFIX)) return null
    const path = imageUrl.slice(PREFIX.length)
    const match = /^(diary|meadow-set|story\/\d{2}-[a-z0-9-]+)\/([a-z0-9-]+\.png)$/.exec(path)
    if (!match) return null
    const [, group, filename] = match
    const kind = filename.split('-')[0]
    const slot = group === 'meadow-set' ? MEADOW_SLOTS[filename] : kind === 'outfit' ? 'top' : kind
    if (!LAYERS.some(([key]) => key === slot)) return null
    return {
        path,
        slot,
        onePiece: kind === 'outfit',
        replacesHair: slot === 'hat' && group !== 'meadow-set',
    }
}

export function getAvatarAppearance(character = {}, availablePaths = new Set()) {
    const layers = LAYERS.flatMap(([slot, zIndex]) => {
        const item = character?.[slot]
        const image = describeWardrobeImage(item?.image_url)
        if (!image || image.slot !== slot || !availablePaths.has(image.path)) return []
        return [{ ...image, zIndex, id: item.id, name: item.name }]
    })
    const hiddenBottom = layers.some((layer) => layer.onePiece)
    return {
        base: layers.some((layer) => layer.replacesHair) ? 'cap-compatible' : 'regular',
        layers: layers.filter((layer) => !(hiddenBottom && layer.slot === 'bottom')),
        hiddenBottom,
    }
}
