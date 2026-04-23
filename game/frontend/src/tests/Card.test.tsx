/** Component tests for the Card and CardBack components. */

import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Card, CardBack } from '../components/Card'
import { RANK_FULL, SUIT_META } from '../components/cardMeta'

describe('Card', () => {
  it('renders sprite coordinates on the element data attributes', () => {
    const { container } = render(<Card card={{ suit: 'coppe', rank: 10 }} />)
    expect(container.firstChild).toHaveAttribute('data-sprite-coords', '9,1')
  })

  it('renders artwork layer', () => {
    const { container } = render(<Card card={{ suit: 'bastoni', rank: 1 }} />)
    expect(container.querySelector('.card-art')).toBeInTheDocument()
  })

  it('has the correct accessible title', () => {
    render(<Card card={{ suit: 'spade', rank: 3 }} />)
    expect(screen.getByTitle(`${RANK_FULL[3]} di ${SUIT_META.spade.label}`)).toBeInTheDocument()
  })

  it('calls onClick when playable and clicked', async () => {
    const onClick = vi.fn()
    render(<Card card={{ suit: 'bastoni', rank: 7, playable: true }} onClick={onClick} />)
    await userEvent.click(screen.getByRole('button'))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('calls onClick when not playable (for illegal move feedback)', async () => {
    const onClick = vi.fn()
    const { container } = render(<Card card={{ suit: 'bastoni', rank: 7, playable: false }} onClick={onClick} />)
    const cardFace = container.firstChild as HTMLElement
    await userEvent.click(cardFace)
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('applies playable class when playable', () => {
    const { container } = render(<Card card={{ suit: 'denara', rank: 2, playable: true }} onClick={vi.fn()} />)
    expect(container.firstChild).toHaveClass('playable')
  })
})

describe('CardBack', () => {
  it('renders without crashing', () => {
    const { container } = render(<CardBack />)
    expect(container.firstChild).toHaveClass('card-back')
  })

  it('applies size classes', () => {
    const { container } = render(<CardBack size="lg" />)
    expect(container.firstChild).toHaveStyle({ width: '5rem', height: '7rem' })
  })
})
