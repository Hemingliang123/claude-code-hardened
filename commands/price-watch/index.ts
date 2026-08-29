import type { Command } from '../../commands.js'

const priceWatch = {
  type: 'local',
  name: 'price-watch',
  description: 'Run the e-commerce price watch collector',
  supportsNonInteractive: true,
  load: () => import('./price-watch.js'),
} satisfies Command

export default priceWatch
