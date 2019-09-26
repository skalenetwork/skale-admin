import React from 'react'
import {Icon} from 'rmwc/Icon';


export default class ContainerIcon extends React.Component {

    getIcon(status) {
        switch (status) {
            case 'running':
            case 'exited':
                return "desktop_mac";
            case 'starting':
                return "cached";
            default:
                //return "widgets";
                return "desktop_mac";
        }
    }

    getClass(status) {
          switch (status) {
            case 'running':
                 return "running-container";
            case 'exited':
                return "error-container";
            case 'starting':
                return "warning-container";
            default:
                return "unknown-container";
        }
    }

    render() {
        return (
            <div className={"md-icon-wrap fl-center "+this.getClass(this.props.status)}>
                <Icon strategy="ligature" className="sm-icon">{this.getIcon(this.props.status)}</Icon>
            </div>
        );
    }
}
