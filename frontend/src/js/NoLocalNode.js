import React from 'react'
import {Link} from 'react-router-dom'

import { Button } from 'rmwc/Button';

export default class NoLocalNode extends React.Component {
  render() {
    return (
      <div className="marg-30">
        <div className="fl-cont fl-center-vert content-center">
          <div className="fl-col fl-grow"></div>
          <div className="fl-col fl-grow text-center new-card">
            <h3 className="g-6 marg-top-md">
              Looks like you do not have SKALE node on this computer
            </h3>
            <h6 className="padd-top-sm g-4 fw-4">
              You could create a new one by pressing the button below
            </h6>
            <Link to='/create-node' className="undec">
              <Button className="marg-top-md" raised>Create node</Button>
            </Link>
            <div className="marg-top-big">
              <a href="/" style={{fontSize: '9pt', color: '#1d87e4'}}>Read about requirements</a>
            </div>
          </div>
          <div className="fl-col fl-grow"></div>
        </div>
      </div>
    )
  }
}