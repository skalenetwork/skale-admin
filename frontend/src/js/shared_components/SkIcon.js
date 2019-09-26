import React from 'react'
import {Icon} from 'rmwc/Icon';


export default class SkIcon extends React.Component {
  render() {
    return (
      <div className="big-icon fl-center" style={{backgroundColor: "rgb(203, 255, 214)"}}>
        <Icon strategy="ligature" className="md-icon"
              style={{color: 'rgb(10, 193, 77)'}}>{this.props.icon}</Icon>
      </div>
    );
  }
}
