import React from 'react'
import {Icon} from 'rmwc/Icon';


export default class ContainerIcon extends React.Component {

  getClass(value) {
    switch (value) {
      case 'test':
        return 'lite-green-icon';
      case 'medium':
        return 'blue-icon';
      case 'small':
        return 'orange-icon';
      case 'tiny':
        return 'lite-green-icon';
      default:
        return 'unknown';
    }
  }

  render() {
    return (
      <div className={"md-icon-wrap fl-center " + this.getClass(this.props.status)}>
        <Icon strategy="ligature" className="sm-icon">offline_bolt</Icon>
      </div>
    );
  }
}
