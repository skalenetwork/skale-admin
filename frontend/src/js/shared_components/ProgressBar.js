import React from 'react'
import { LinearProgress } from 'rmwc/LinearProgress';

export default class ProgressBar extends React.Component {
  render() {
    return (
      <div className="marg-30">
        <div className="fl-cont fl-center-vert content-center">
          <div className="fl-col fl-grow"></div>
          <div className="fl-col fl-grow text-center">
            <LinearProgress determinate={false}></LinearProgress>
          </div>
          <div className="fl-col fl-grow"></div>
        </div>
      </div>
    )
  }
}