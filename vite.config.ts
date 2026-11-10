import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Hosted under a sub-path (ibiraheel.com/demos/parcel-sort-cell-sizer/).
// Data fetches use import.meta.env.BASE_URL, so they follow this setting.
export default defineConfig({
  base: '/demos/parcel-sort-cell-sizer/',
  plugins: [react()],
})
